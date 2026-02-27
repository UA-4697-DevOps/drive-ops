FROM alpine:3.19

# Create a non-root user/group and install dependencies
RUN addgroup -S backup && adduser -S -G backup backup \
    && apk add --no-cache bash postgresql15-client aws-cli

# Copy the backup script into the container
COPY backup.sh /usr/local/bin/backup.sh

# Ensure the script is executable
RUN chmod +x /usr/local/bin/backup.sh

# Drop root privileges by switching to the newly created user
USER backup

# Set the script as the container's entrypoint
ENTRYPOINT ["/usr/local/bin/backup.sh"]
