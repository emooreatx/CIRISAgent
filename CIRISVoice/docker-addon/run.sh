#!/usr/bin/with-contenv bashio

# CIRIS Wyoming Bridge startup script for Home Assistant Add-on

bashio::log.info "Starting CIRIS Wyoming Bridge..."

# Read configuration from add-on options
CIRIS_URL=$(bashio::config 'ciris_url')
CIRIS_API_KEY=$(bashio::config 'ciris_api_key')
CIRIS_TIMEOUT=$(bashio::config 'ciris_timeout')
CIRIS_CHANNEL=$(bashio::config 'ciris_channel')
STT_PROVIDER=$(bashio::config 'stt_provider')
TTS_PROVIDER=$(bashio::config 'tts_provider')
TTS_VOICE=$(bashio::config 'tts_voice')
LOG_LEVEL=$(bashio::config 'log_level')

# Export for Python
export CIRIS_API_URL="${CIRIS_URL}"
export CIRIS_API_INTERACTION_TIMEOUT="${CIRIS_TIMEOUT}"

# Handle API key - check secrets first, then config
if bashio::config.has_value 'ciris_api_key'; then
    export CIRIS_API_KEY="${CIRIS_API_KEY}"
else
    # Try to get from HA secrets
    if bashio::config.exists 'ciris_api_key'; then
        export CIRIS_API_KEY=$(bashio::secrets 'ciris_api_key')
    fi
fi

# Get provider API keys from secrets
if [[ "${STT_PROVIDER}" == "openai" ]] || [[ "${TTS_PROVIDER}" == "openai" ]]; then
    export OPENAI_API_KEY=$(bashio::secrets 'openai_api_key' || echo "")
fi

if [[ "${STT_PROVIDER}" == "google" ]] || [[ "${TTS_PROVIDER}" == "google" ]]; then
    export GOOGLE_APPLICATION_CREDENTIALS="/config/google_cloud_key.json"
fi

# Create configuration file
bashio::log.info "Creating configuration..."
cat > /app/config.yaml <<EOF
# Auto-generated configuration
wyoming:
  host: "0.0.0.0"
  port: 10300
  timeout: 60

ciris:
  api_url: "${CIRIS_URL}"
  api_key: "${CIRIS_API_KEY}"
  timeout: ${CIRIS_TIMEOUT}
  channel_id: "${CIRIS_CHANNEL}"
  profile: "ha_addon"
  language: "en-US"

stt:
  provider: "${STT_PROVIDER}"
  model: "whisper-1"
  language: "en"
  google_credentials_path: "/config/google_cloud_key.json"
  google_language_code: "en-US"

tts:
  provider: "${TTS_PROVIDER}"
  model: "tts-1"
  voice: "${TTS_VOICE}"
  speed: 1.0
  google_credentials_path: "/config/google_cloud_key.json"
  google_voice_name: "${TTS_VOICE}"

logging:
  level: "${LOG_LEVEL}"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
EOF

bashio::log.info "Configuration created"
bashio::log.info "CIRIS URL: ${CIRIS_URL}"
bashio::log.info "Timeout: ${CIRIS_TIMEOUT} seconds"
bashio::log.info "STT Provider: ${STT_PROVIDER}"
bashio::log.info "TTS Provider: ${TTS_PROVIDER}"
bashio::log.info "TTS Voice: ${TTS_VOICE}"

# Change to app directory
cd /app

# Start the Wyoming bridge
bashio::log.info "Starting Wyoming bridge on port 10300..."
exec python3 -m src.bridge