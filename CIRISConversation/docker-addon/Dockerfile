ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and dependencies
RUN \
    apk add --no-cache \
        python3 \
        py3-pip \
        py3-yaml \
    && pip3 install --no-cache-dir --upgrade pip

# Create app directory
WORKDIR /app

# Copy requirements
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application
COPY src /app/src

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

# Labels
LABEL \
    io.hass.name="CIRIS Conversation Agent" \
    io.hass.description="CIRIS AI conversation agent for Home Assistant" \
    io.hass.type="addon" \
    io.hass.version="1.0.0" \
    io.hass.arch="aarch64|amd64"

# Run
CMD [ "/run.sh" ]