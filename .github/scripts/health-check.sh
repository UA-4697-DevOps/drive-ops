set -euo pipefail

# Allow overriding variables, use defaults if not provided
MAX_ATTEMPTS=${MAX_ATTEMPTS:-5}
DELAY=${DELAY:-10}
PORT=${HEALTH_PORT:-8080}
ENDPOINT=${HEALTH_ENDPOINT:-/health}
URL="http://localhost:${PORT}${ENDPOINT}"

echo ">>> Running health check against ${URL}..."
for i in $(seq 1 $MAX_ATTEMPTS); do
  echo "  Attempt ${i}/${MAX_ATTEMPTS}..."
  HTTP_CODE=$(curl -sf -o /tmp/health_body.json -w '%{http_code}' "${URL}" 2>/dev/null || echo "000")

  if [ "$HTTP_CODE" = "200" ]; then
    BODY=$(cat /tmp/health_body.json)
    STATUS=$(jq -r '.status // empty' /tmp/health_body.json)
    
    if [ "$STATUS" = "ok" ] || [ "$STATUS" = "healthy" ]; then
      echo ">>> Health check passed: ${BODY}"
      exit 0
    else
      echo "  Unexpected response body: ${BODY}"
    fi
  else
    echo "  HTTP ${HTTP_CODE}"
  fi

  [ "$i" -lt "$MAX_ATTEMPTS" ] && sleep "$DELAY"
done

echo "Health check failed after ${MAX_ATTEMPTS} attempts" >&2
exit 1