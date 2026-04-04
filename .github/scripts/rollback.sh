set -euo pipefail

# Ensure the previous image is actually provided
if [ -z "${PREV_IMAGE:-}" ] || [ "${PREV_IMAGE}" = "none" ]; then
  echo "No previous image recorded — cannot rollback" >&2
  exit 1
fi

echo ">>> Pulling previous image ${PREV_IMAGE}..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
docker pull "${PREV_IMAGE}"

echo ">>> Rolling back ${SERVICE}..."
IMAGE="${PREV_IMAGE}" docker compose up -d --no-deps --force-recreate "${SERVICE}"

echo ">>> Waiting for container health status..."
for i in {1..24}; do
  HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER}" 2>/dev/null || echo "missing")
  if [ "$HEALTH" = "healthy" ]; then
    echo "Rollback container is healthy!"
    exit 0
  fi
  sleep 5
done

echo "Rollback container did not become healthy in time." >&2
docker logs --tail 30 "${CONTAINER}" >&2
exit 1