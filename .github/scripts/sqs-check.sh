set -euo pipefail

# If no queues are specified, just exit successfully
if [ -z "${SQS_QUEUES:-}" ]; then
  echo "No SQS queues specified. Skipping SQS connectivity check."
  exit 0
fi

echo "Checking SQS queue connectivity from EC2 instance..."
FAILED=0

# Convert comma-separated string to an array
IFS=',' read -r -a QUEUE_ARRAY <<< "$SQS_QUEUES"

for QUEUE_NAME in "${QUEUE_ARRAY[@]}"; do
  # Trim whitespace
  QUEUE_NAME=$(echo "$QUEUE_NAME" | xargs) 
  if [ -z "$QUEUE_NAME" ]; then continue; fi

  QUEUE_URL=$(aws sqs get-queue-url \
    --queue-name "$QUEUE_NAME" \
    --region "${AWS_REGION}" \
    --query 'QueueUrl' --output text 2>/dev/null) || true

  if [ -z "$QUEUE_URL" ] || [ "$QUEUE_URL" = "None" ]; then
    echo "[WARN] $QUEUE_NAME - not found"
    FAILED=1
    continue
  fi

  # Lightweight attribute fetch to confirm IAM permissions
  ATTRS=$(aws sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --region "${AWS_REGION}" \
    --attribute-names ApproximateNumberOfMessages \
    --query 'Attributes.ApproximateNumberOfMessages' \
    --output text 2>/dev/null) || true

  if [ -n "$ATTRS" ] && [ "$ATTRS" != "None" ]; then
    echo "[OK] $QUEUE_NAME - accessible (msgs: $ATTRS)"
  else
    echo "[WARN] $QUEUE_NAME - cannot read attributes (access denied)"
    FAILED=1
  fi
done

if [ "$FAILED" -eq 0 ]; then
  echo "All specified SQS queues are accessible."
  exit 0
else
  echo "One or more SQS queues are not accessible." >&2
  exit 1
fi