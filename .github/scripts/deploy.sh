set -euo pipefail

echo ">>> Fetching configuration for ${SERVICE} in ${DEPLOY_ENV}..."
ENV_VARS=$(aws secretsmanager get-secret-value \
  --secret-id "drive-ops/${DEPLOY_ENV}/${SERVICE}/env-file" \
  --region "${AWS_REGION}" \
  --query 'SecretString' --output text)

echo ">>> Authenticating with ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo ">>> Pulling image ${IMAGE}..."
docker pull "${IMAGE}"

echo ">>> Updating .env..."
echo "$ENV_VARS" > .env

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