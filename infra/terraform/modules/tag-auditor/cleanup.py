import boto3
import os


def cleanup_untagged_resources(region, dry_run=True):
    """
    Finds and optionally terminates fully untagged EC2 instances.
    dry_run=True (default) - only logs, never deletes.
    dry_run=False - real termination.
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


def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "us-east-2")
    sns_arn = os.environ.get("SNS_TOPIC_ARN")

    if not sns_arn:
        raise ValueError("SNS_TOPIC_ARN environment variable is not set.")

    dry_run = event.get("dry_run", True)
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

    return {
        "statusCode": 200,
        "dry_run": dry_run,
        "forgotten_count": len(forgotten),
    }