import boto3
import os

MANDATORY_TAGS = ["Project", "Environment", "ManagedBy", "CostCenter"]
SNS_MAX_BYTES = 256 * 1024


def get_ec2_arns(ec2, region, account_id):
    arns = []
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate():
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
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
    for arn in all_arns:
        existing_tags = tags_by_arn.get(arn, set())
        missing_tags = [t for t in MANDATORY_TAGS if t not in existing_tags]
        if missing_tags:
            non_compliant.append({"arn": arn, "missing_tags": missing_tags})

    return non_compliant


def cleanup_untagged_resources(region, dry_run=True):
    """
    Finds and optionally terminates fully untagged EC2 instances.
    dry_run=True (default) - only logs, never deletes.
    dry_run=False - real termination, triggered manually via event.
    """
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    ec2 = boto3.client("ec2", region_name=region)
    tagging = boto3.client("resourcegroupstaggingapi", region_name=region)

    tagged_arns = set()
    paginator = tagging.get_paginator("get_resources")
    for page in paginator.paginate(ResourcesPerPage=100):
        for resource in page["ResourceTagMappingList"]:
            tagged_arns.add(resource["ResourceARN"])

    forgotten = []
    for page in ec2.get_paginator("describe_instances").paginate():
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                instance_id = instance["InstanceId"]
                arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"
                state = instance["State"]["Name"]

                if state in ("terminated", "shutting-down"):
                    continue

                if arn not in tagged_arns:
                    forgotten.append({"arn": arn, "instance_id": instance_id, "state": state})
                    if dry_run:
                        print(f"[DRY-RUN] Would terminate: {instance_id} (state: {state})")
                    else:
                        print(f"[CLEANUP] Terminating: {instance_id}")
                        ec2.terminate_instances(InstanceIds=[instance_id])

    return forgotten


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

    if not sns_arn:
        raise ValueError("SNS_TOPIC_ARN environment variable is not set.")

    action = event.get("action", "audit")
    dry_run = event.get("dry_run", True)

    if action == "cleanup":
        mode = "DRY-RUN" if dry_run else "LIVE"
        print(f"Starting cleanup in {mode} mode, region: {region}")
        forgotten = cleanup_untagged_resources(region, dry_run=dry_run)
        print(f"Cleanup complete. Forgotten resources: {len(forgotten)}")

        if forgotten:
            sns = boto3.client("sns", region_name=region)
            lines = [f"Cleanup Report [{mode}] - {len(forgotten)} forgotten resource(s)\n"]
            for r in forgotten:
                lines.append(f"Resource: {r['arn']} (state: {r['state']})")
            sns.publish(
                TopicArn=sns_arn,
                Subject=f"[drive-ops] Cleanup [{mode}]: Forgotten Resources",
                Message="\n".join(lines),
            )

        return {"statusCode": 200, "action": "cleanup", "dry_run": dry_run, "forgotten_count": len(forgotten)}

    print(f"Starting tag audit in region: {region}")
    print(f"Mandatory tags: {MANDATORY_TAGS}")
    non_compliant = get_non_compliant_resources(region)
    print(f"Audit complete. Non-compliant resources: {len(non_compliant)}")

    if non_compliant:
        publish_to_sns(sns_arn, non_compliant, region)
    else:
        print("All resources are compliant. No SNS notification needed.")

    return {"statusCode": 200, "action": "audit", "non_compliant_count": len(non_compliant)}

