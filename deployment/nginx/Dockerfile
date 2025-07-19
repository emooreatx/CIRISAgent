FROM nginx:alpine

# Install certbot for Let's Encrypt
RUN apk add --no-cache certbot certbot-nginx

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our nginx configuration
# Use ARG to determine which config to use
ARG NGINX_CONFIG=agents.ciris.ai-dev.conf
COPY ${NGINX_CONFIG} /etc/nginx/conf.d/agents.ciris.ai.conf

# Create directories for logs
RUN mkdir -p /var/log/nginx

# SSL certificates will be mounted as volumes
# Let's Encrypt certificates: /etc/letsencrypt
# DH params: /etc/letsencrypt/ssl-dhparams.pem

# Expose ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]