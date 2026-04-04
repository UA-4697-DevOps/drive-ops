set -euo pipefail

REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
REPO="${REGISTRY}/${ECR_REPOSITORY}"

if [ -n "${IMAGE_TAG_INPUT:-}" ]; then
  TAG="${IMAGE_TAG_INPUT}"
else
  # Fetch the latest image tag pushed to ECR, preferring deterministic sha-* tags
  LATEST_IMAGE=$(aws ecr describe-images \
    --repository-name "${ECR_REPOSITORY}" \
    --query 'sort_by(imageDetails,& imagePushedAt)[-1]' \
    --output json)
  
  # Try to find a sha-* tag (most deterministic)
  TAG=$(echo "$LATEST_IMAGE" | jq -r '.imageTags[] | select(. | startswith("sha-")) | .' | head -1)
  
  # Fallbacks if no sha-* tag is found
  if [ -z "$TAG" ] || [ "$TAG" = "null" ]; then
    IMAGE_DIGEST=$(echo "$LATEST_IMAGE" | jq -r '.imageDigest // empty')
    if [ -n "$IMAGE_DIGEST" ]; then
      TAG=$(aws ecr batch-get-image \
        --repository-name "${ECR_REPOSITORY}" \
        --image-ids imageDigest="$IMAGE_DIGEST" \
        --query 'images[0].imageId.imageTag // images[0].imageId.imageDigest' \
        --output text)
    else
      TAG=$(echo "$LATEST_IMAGE" | jq -r '.imageTags[0] // empty')
    fi
  fi
  
  if [ -z "$TAG" ] || [ "$TAG" = "None" ]; then
    echo "::error::No images found in ECR repository ${ECR_REPOSITORY}"
    exit 1
  fi
fi

# Write to GitHub Actions outputs
echo "image_uri=${REPO}:${TAG}" >> "$GITHUB_OUTPUT"
echo "image_tag=${TAG}" >> "$GITHUB_OUTPUT"
echo "### 🐳 Image to deploy" >> "$GITHUB_STEP_SUMMARY"
echo "\`${REPO}:${TAG}\`" >> "$GITHUB_STEP_SUMMARY"