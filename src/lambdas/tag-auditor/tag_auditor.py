import boto3
import json
import os

tags_env = os.environ.get("MANDATORY_TAGS", "Project,Environment,ManagedBy,CostCenter")
MANDATORY_TAGS = [t.strip() for t in tags_env.split(",")]
SNS_MAX_BYTES = 256 * 1024


def get_ec2_arns(ec2, region, account_id):
    arns = []
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate():
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                # Skip EKS node group instances (part of ASG, will restart if terminated)
                tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                if "eks:nodegroup-name" in tags or "aws:autoscaling:groupName" in tags:
                    continue
                arns.append(f"arn:aws:ec2:{region}:{account_id}:instance/{instance['InstanceId']}")
    return arns


def get_rds_arns(rds):
    arns = []
    paginator = rds.get_paginator("describe_db_instances")
    for page in paginator.paginate():
        for db in page["DBInstances"]:
            arns.append(db["DBInstanceArn"])
    return arns


def get_sqs_arns(sqs):
    arns = []
    paginator = sqs.get_paginator("list_queues")
    for page in paginator.paginate():
        for url in page.get("QueueUrls", []):
            attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["QueueArn"])
            arns.append(attrs["Attributes"]["QueueArn"])
    return arns


def get_secrets_arns(sm):
    arns = []
    paginator = sm.get_paginator("list_secrets")
    for page in paginator.paginate():
        for secret in page["SecretList"]:
            arns.append(secret["ARN"])
    return arns


def get_non_compliant_resources(region):
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    ec2 = boto3.client("ec2", region_name=region)
    rds = boto3.client("rds", region_name=region)
    sqs = boto3.client("sqs", region_name=region)
    sm = boto3.client("secretsmanager", region_name=region)
    tagging = boto3.client("resourcegroupstaggingapi", region_name=region)

    all_arns = set()
    all_arns.update(get_ec2_arns(ec2, region, account_id))
    all_arns.update(get_rds_arns(rds))
    all_arns.update(get_sqs_arns(sqs))
    all_arns.update(get_secrets_arns(sm))

    tags_by_arn = {}
    paginator = tagging.get_paginator("get_resources")
    for page in paginator.paginate(ResourcesPerPage=100):
        for resource in page["ResourceTagMappingList"]:
            arn = resource["ResourceARN"]
            tags_by_arn[arn] = {t["Key"] for t in resource.get("Tags", [])}

    non_compliant = []
    untagged_ec2_instance_ids = []

    for arn in all_arns:
        existing_tags = tags_by_arn.get(arn, set())
        missing_tags = [t for t in MANDATORY_TAGS if t not in existing_tags]
        if missing_tags:
            non_compliant.append({"arn": arn, "missing_tags": missing_tags})
            # Collect fully untagged EC2 instances for cleanup invocation
            if "ec2" in arn and "instance" in arn and not existing_tags:
                instance_id = arn.split("/")[-1]
                untagged_ec2_instance_ids.append(instance_id)

    return non_compliant, untagged_ec2_instance_ids


def invoke_cleanup(lambda_client, cleanup_function_name, instance_ids, dry_run):
    payload = {
        "instance_ids": instance_ids,
        "dry_run": dry_run,
    }
    print(f"Invoking cleanup Lambda with {len(instance_ids)} instance(s), dry_run={dry_run}")
    lambda_client.invoke(
        FunctionName=cleanup_function_name,
        InvocationType="Event",  # async
        Payload=json.dumps(payload),
    )


def build_chunks(non_compliant, total):
    chunks = []
    current_lines = []
    current_size = 0
    header = f"Tag Audit Report - {total} non-compliant resource(s) found\n\n"

    for r in non_compliant:
        entry = f"Resource: {r['arn']}\nMissing tags: {', '.join(r['missing_tags'])}\n\n"
        entry_size = len(entry.encode("utf-8"))
        if current_size + entry_size > SNS_MAX_BYTES - len(header.encode("utf-8")):
            chunks.append(header + "".join(current_lines))
            current_lines = []
            current_size = 0
        current_lines.append(entry)
        current_size += entry_size

    if current_lines:
        chunks.append(header + "".join(current_lines))

    return chunks


def publish_to_sns(sns_arn, non_compliant, region):
    sns = boto3.client("sns", region_name=region)
    chunks = build_chunks(non_compliant, len(non_compliant))
    for i, message in enumerate(chunks):
        subject = "[drive-ops] Tag Audit: Non-Compliant Resources Found"
        if len(chunks) > 1:
            subject += f" ({i + 1}/{len(chunks)})"
        sns.publish(TopicArn=sns_arn, Subject=subject, Message=message)
        print(f"Published SNS chunk {i + 1}/{len(chunks)}")


def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "us-east-2")
    sns_arn = os.environ.get("SNS_TOPIC_ARN")
    cleanup_function_name = os.environ.get("CLEANUP_FUNCTION_NAME")
    dry_run = event.get("dry_run", True)

    if not sns_arn:
        raise ValueError("SNS_TOPIC_ARN environment variable is not set.")

    print(f"Starting tag audit in region: {region}")
    print(f"Mandatory tags: {MANDATORY_TAGS}")

    non_compliant, untagged_ec2_instance_ids = get_non_compliant_resources(region)
    print(f"Audit complete. Non-compliant resources: {len(non_compliant)}")

    if non_compliant:
        publish_to_sns(sns_arn, non_compliant, region)

        # Invoke cleanup Lambda if there are fully untagged EC2 instances
        if untagged_ec2_instance_ids and cleanup_function_name:
            lambda_client = boto3.client("lambda", region_name=region)
            invoke_cleanup(lambda_client, cleanup_function_name, untagged_ec2_instance_ids, dry_run)
    else:
        print("All resources are compliant. No SNS notification needed.")

    return {
        "statusCode": 200,
        "non_compliant_count": len(non_compliant),
        "untagged_ec2_count": len(untagged_ec2_instance_ids),
    }