set -euo pipefail

echo ">>> Fetching configuration from SSM Parameter Store..."
TRIP_URL=$(aws ssm get-parameter \
  --name "/drive-ops/${DEPLOY_ENV}/client-gateway/trip-service-url" \
  --region "${AWS_REGION}" \
  --query 'Parameter.Value' --output text)

DRIVER_URL=$(aws ssm get-parameter \
  --name "/drive-ops/${DEPLOY_ENV}/client-gateway/driver-service-url" \
  --region "${AWS_REGION}" \
  --query 'Parameter.Value' --output text)

echo ">>> Fetching secrets from Secrets Manager..."
BOT_TOKEN=$(aws secretsmanager get-secret-value \
  --secret-id "drive-ops/${DEPLOY_ENV}/client-gateway/telegram-token" \
  --region "${AWS_REGION}" \
  --query 'SecretString' --output text)

for VAR_NAME in TRIP_URL DRIVER_URL BOT_TOKEN; do
  if [ -z "${!VAR_NAME}" ] || [ "${!VAR_NAME}" = "None" ]; then
    echo "Failed to retrieve ${VAR_NAME}" >&2
    exit 1
  fi
done
echo ">>> Configuration retrieved successfully"

echo ">>> Authenticating with ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo ">>> Pulling image ${IMAGE}..."
docker pull "${IMAGE}"

echo ">>> Updating .env with fetched configuration..."
touch .env
for VAR_LINE in \
  "TRIP_SERVICE_URL=${TRIP_URL}" \
  "DRIVER_SERVICE_URL=${DRIVER_URL}" \
  "TELEGRAM_BOT_TOKEN=${BOT_TOKEN}"; do
  VAR_KEY="${VAR_LINE%%=*}"
  grep -v "^${VAR_KEY}=" .env > .env.tmp || true
  mv .env.tmp .env
  printf '%s\n' "${VAR_LINE}" >> .env
done

echo ">>> Deploying ${SERVICE}..."
IMAGE="${IMAGE}" docker compose up -d --no-deps --force-recreate "${SERVICE}"

echo ">>> Waiting for container to become healthy..."
SECONDS=0
TIMEOUT=120
while [ $SECONDS -lt $TIMEOUT ]; do
  HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER}" 2>/dev/null || echo "missing")
  if [ "$HEALTH" = "healthy" ]; then
    echo ">>> Container is healthy after ${SECONDS}s"
    exit 0
  elif [ "$HEALTH" = "unhealthy" ]; then
    echo "Container entered unhealthy state" >&2
    docker logs --tail 30 "${CONTAINER}" >&2
    exit 1
  fi
  sleep 5
done

echo "Container did not become healthy within ${TIMEOUT}s" >&2
docker logs --tail 30 "${CONTAINER}" >&2
exit 1