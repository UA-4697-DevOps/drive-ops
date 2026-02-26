import boto3
import os


def terminate_instances(ec2, instance_ids, dry_run):
    """
    Terminates EC2 instances by ID.
    dry_run=True - only logs, never deletes.
    dry_run=False - real termination.
    """
    for instance_id in instance_ids:
        if dry_run:
            print(f"[DRY-RUN] Would terminate: {instance_id}")
        else:
            print(f"[CLEANUP] Terminating: {instance_id}")
            ec2.terminate_instances(InstanceIds=[instance_id])


def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "us-east-2")
    sns_arn = os.environ.get("SNS_TOPIC_ARN")

    if not sns_arn:
        raise ValueError("SNS_TOPIC_ARN environment variable is not set.")

    # Receive instance IDs from tag_auditor via Lambda invoke
    instance_ids = event.get("instance_ids", [])
    dry_run = event.get("dry_run", True)
    mode = "DRY-RUN" if dry_run else "LIVE"

    if not instance_ids:
        print("No instance IDs provided. Nothing to clean up.")
        return {"statusCode": 200, "dry_run": dry_run, "terminated_count": 0}

    print(f"Starting cleanup in {mode} mode, region: {region}")
    print(f"Instances to process: {instance_ids}")

    ec2 = boto3.client("ec2", region_name=region)
    terminate_instances(ec2, instance_ids, dry_run)

    if not dry_run:
        sns = boto3.client("sns", region_name=region)
        lines = [f"Cleanup Report [{mode}] - {len(instance_ids)} instance(s) terminated\n"]
        for instance_id in instance_ids:
            lines.append(f"Terminated: {instance_id}")
        sns.publish(
            TopicArn=sns_arn,
            Subject=f"[drive-ops] Cleanup [{mode}]: Instances Terminated",
            Message="\n".join(lines),
        )

    return {
        "statusCode": 200,
        "dry_run": dry_run,
        "terminated_count": len(instance_ids),
    }