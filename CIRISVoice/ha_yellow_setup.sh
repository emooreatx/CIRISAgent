#!/bin/sh
# CIRIS Wyoming Bridge Setup Script for Home Assistant Yellow
# Run this in Terminal & SSH on your HA Yellow

echo "CIRIS Wyoming Bridge Setup for HA Yellow"
echo "========================================"
echo ""

# Configuration
REPO_URL="https://github.com/CIRISAI/CIRISAgent.git"  # Update with your repo URL
BRANCH="main"  # Change if using different branch
ADDON_NAME="ciris-wyoming"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo "${RED}[✗]${NC} $1"
}

# Check if we're in the right place
if [ ! -d "/config" ]; then
    print_error "This script must be run from Home Assistant Terminal & SSH"
    exit 1
fi

# Step 1: Install dependencies
print_status "Installing required packages..."
apk update
apk add --no-cache git

# Step 2: Create addons directory
print_status "Creating local addons directory..."
mkdir -p /addons

# Step 3: Clone or update repository
if [ -d "/addons/$ADDON_NAME" ]; then
    print_warning "Addon directory exists. Updating..."
    cd /addons/$ADDON_NAME
    
    # Save any local changes
    if [ -f "config.yaml" ]; then
        cp config.yaml config.yaml.backup
        print_status "Backed up existing config to config.yaml.backup"
    fi
    
    # Pull latest changes
    git pull origin $BRANCH
else
    print_status "Cloning CIRIS repository..."
    cd /addons
    git clone $REPO_URL temp
    
    # Copy only what we need
    print_status "Setting up addon structure..."
    mkdir -p $ADDON_NAME
    
    # Copy the Python application files
    cp -r temp/CIRISVoice/src $ADDON_NAME/
    cp temp/CIRISVoice/requirements.txt $ADDON_NAME/
    cp temp/CIRISVoice/config.example.yaml $ADDON_NAME/
    
    # Copy the addon Docker files
    cp temp/CIRISVoice/docker-addon/* $ADDON_NAME/
    
    rm -rf temp
fi

# Step 4: Verify structure
cd /addons/$ADDON_NAME
print_status "Verifying addon structure..."

# Check required files
REQUIRED_FILES="config.yaml Dockerfile run.sh build.yaml"
MISSING_FILES=""

for file in $REQUIRED_FILES; do
    if [ ! -f "$file" ]; then
        MISSING_FILES="$MISSING_FILES $file"
    fi
done

if [ -n "$MISSING_FILES" ]; then
    print_error "Missing required files:$MISSING_FILES"
    print_warning "Attempting to fix..."
    
    # If docker-addon files are in subdirectory, move them up
    if [ -d "docker-addon" ]; then
        cp docker-addon/* . 2>/dev/null || true
    fi
fi

# Step 5: Update config with user settings
print_status "Configuring addon..."

# Check if google_cloud_key.json exists
if [ -f "/config/google_cloud_key.json" ]; then
    print_status "Found Google Cloud key at /config/google_cloud_key.json"
else
    print_warning "Google Cloud key not found. You'll need to configure STT/TTS provider."
fi

# Create a setup summary file
cat > /config/ciris_wyoming_setup.txt << EOF
CIRIS Wyoming Bridge Setup Complete!
===================================

Next Steps:

1. Go to Settings → Add-ons → Add-on Store
2. Click the menu (⋮) → Check for updates
3. Look for "CIRIS Wyoming Bridge" in Local add-ons
4. Click on it and:
   - Install the add-on
   - Configure your CIRIS API URL
   - Start the add-on

5. Configure Voice Pipeline:
   - Settings → Voice assistants
   - Add new assistant "CIRIS"
   - Set timeout to 60 seconds
   - Select Wyoming for STT/TTS

6. Assign to Voice PE pucks:
   - Settings → Devices → ESPHome
   - Select your Voice PE device
   - Configure → Select CIRIS pipeline

Configuration needed in addon:
- CIRIS API URL: http://YOUR_CIRIS_IP:8080
- Timeout: 58 seconds
- STT Provider: google (if using Google Cloud)
- TTS Provider: google (if using Google Cloud)

Your Google Cloud key is at: /config/google_cloud_key.json

For help, see: /addons/$ADDON_NAME/VOICE_PE_QUICKSTART.md
EOF

print_status "Setup complete! Check /config/ciris_wyoming_setup.txt for next steps."

# Step 6: Show summary
echo ""
echo "Summary:"
echo "--------"
print_status "Addon location: /addons/$ADDON_NAME"
print_status "Google key: /config/google_cloud_key.json"
print_status "Next: Install addon from HA UI"
echo ""
echo "To update in the future, run this script again!"