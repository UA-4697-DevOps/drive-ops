# ---------------------------------------------------------------------------
# web-client Dockerfile
#
# Serves the static DriveOps dashboard via nginx on port 8083.
# Proxies /api/* requests to the driver-service at runtime.
#
# The official nginx image processes templates in /etc/nginx/templates/
# using envsubst before starting nginx, so DRIVER_SERVICE_URL is injected
# at container startup without a custom entrypoint script.
# ---------------------------------------------------------------------------

FROM nginx:1.27-alpine

# Install curl for healthcheck (nginx-alpine doesn't include it by default)
RUN apk add --no-cache curl

# Copy static web assets
COPY --chown=nginx:nginx ./index.html     /usr/share/nginx/html/index.html
COPY --chown=nginx:nginx ./css            /usr/share/nginx/html/css
COPY --chown=nginx:nginx ./js             /usr/share/nginx/html/js

# Copy nginx config template — nginx's entrypoint will run envsubst on it
# and write the result to /etc/nginx/conf.d/default.conf before startup.
COPY ./nginx/default.conf.template /etc/nginx/templates/default.conf.template

# Runtime environment: URL of the driver-service reachable from within the
# container network (Docker Compose service name or K8s ClusterIP DNS name).
# ARG lets the default be overridden at build time via --build-arg.
ARG DRIVER_SERVICE_URL=http://driver-service:8082
ENV DRIVER_SERVICE_URL=$DRIVER_SERVICE_URL

# nginx image already runs as nginx user (UID 101) for the worker processes.
# The master process must run as root, which is the nginx image default.

EXPOSE 8083

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8083/health || exit 1
