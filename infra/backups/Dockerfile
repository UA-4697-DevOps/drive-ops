FROM alpine:3.19

# Install dependencies: bash, postgresql client, and aws-cli
RUN apk add --no-cache bash postgresql15-client aws-cli

# Copy the backup script into the container
COPY backup.sh /usr/local/bin/backup.sh

# Ensure the script is executable
RUN chmod +x /usr/local/bin/backup.sh

# Set the script as the container's entrypoint
ENTRYPOINT ["/usr/local/bin/backup.sh"]
