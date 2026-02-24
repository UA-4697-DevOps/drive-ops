import boto3
import os

MANDATORY_TAGS = ["Project", "Environment", "ManagedBy", "CostCenter"]

# Resource types to audit via Tagging API
RESOURCE_TYPES = [
    "ec2:instance",
    "rds:db",
    "sqs:queue",
    "secretsmanager:secret",
]


def get_non_compliant_resources(region: str) -> list[dict]:
    """
    Scans AWS resources using the Tagging API and returns
    a list of resources missing one or more mandatory tags.
    """
    tagging = boto3.client("resourcegroupstaggingapi", region_name=region)
    non_compliant = []

    paginator = tagging.get_paginator("get_resources")
    pages = paginator.paginate(
        ResourceTypeFilters=RESOURCE_TYPES,
        ResourcesPerPage=100,
    )

    for page in pages:
        for resource in page["ResourceTagMappingList"]:
            arn = resource["ResourceARN"]
            existing_tags = {t["Key"] for t in resource.get("Tags", [])}
            missing_tags = [t for t in MANDATORY_TAGS if t not in existing_tags]

            if missing_tags:
                non_compliant.append({
                    "arn": arn,
                    "missing_tags": missing_tags,
                })

    return non_compliant


def publish_to_sns(sns_arn: str, non_compliant: list[dict], region: str) -> None:
    """
    Publishes a formatted audit report to SNS.
    """
    sns = boto3.client("sns", region_name=region)

    lines = [f"Tag Audit Report - {len(non_compliant)} non-compliant resource(s) found\n"]
    for r in non_compliant:
        lines.append(f"Resource: {r['arn']}")
        lines.append(f"Missing tags: {', '.join(r['missing_tags'])}\n")

    message = "\n".join(lines)

    sns.publish(
        TopicArn=sns_arn,
        Subject="[drive-ops] Tag Audit: Non-Compliant Resources Found",
        Message=message,
    )
    print(f"Published SNS alert for {len(non_compliant)} non-compliant resources.")


def lambda_handler(event, context):
    region = os.environ.get("AWS_REGION", "us-east-2")
    sns_arn = os.environ.get("SNS_TOPIC_ARN")

    if not sns_arn:
        raise ValueError("SNS_TOPIC_ARN environment variable is not set.")

    print(f"Starting tag audit in region: {region}")
    print(f"Mandatory tags: {MANDATORY_TAGS}")
    print(f"Resource types: {RESOURCE_TYPES}")

    non_compliant = get_non_compliant_resources(region)
    print(f"Audit complete. Non-compliant resources: {len(non_compliant)}")

    if non_compliant:
        publish_to_sns(sns_arn, non_compliant, region)
    else:
        print("All resources are compliant. No SNS notification needed.")

    return {
        "statusCode": 200,
        "non_compliant_count": len(non_compliant),
    }
