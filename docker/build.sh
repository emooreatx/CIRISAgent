#!/bin/bash
# CIRIS Docker Build Script with Mac Support

echo "CIRIS Docker Build Script"
echo "========================"

# Detect platform
PLATFORM=$(uname -s)
ARCH=$(uname -m)

echo "Detected platform: $PLATFORM ($ARCH)"

# Check if running on Mac with Apple Silicon
if [[ "$PLATFORM" == "Darwin" ]] && [[ "$ARCH" == "arm64" ]]; then
    echo ""
    echo "⚠️  Apple Silicon Mac detected!"
    echo "Building with platform flag for compatibility..."
    echo ""
    PLATFORM_FLAG="--platform linux/amd64"
else
    PLATFORM_FLAG=""
fi

# Function to build with proper platform support
build_image() {
    local dockerfile=$1
    local tag=$2
    
    echo "Building $tag..."
    docker build $PLATFORM_FLAG -f "$dockerfile" -t "$tag" . || {
        echo "❌ Build failed!"
        echo ""
        echo "If you're on Mac and seeing psutil/gcc errors, try:"
        echo "1. Ensure Docker Desktop is updated to the latest version"
        echo "2. Enable 'Use Rosetta for x86/amd64 emulation' in Docker Desktop settings"
        echo "3. Increase Docker memory allocation to at least 4GB"
        echo ""
        return 1
    }
    echo "✅ Successfully built $tag"
}

# Main build selection
echo ""
echo "Which build would you like to use?"
echo "1) Build and deploy mock container with dev GUI (recommended for development)"
echo "2) Standard build (with gcc for psutil)"
echo "3) Optimized multi-stage build (smaller image)"
echo "4) Build both standard and optimized"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "Building and deploying mock container with dev GUI..."
        build_image "docker/Dockerfile" "ciris:latest"
        if [ $? -eq 0 ]; then
            echo ""
            echo "Starting mock API and GUI services..."
            docker-compose -f docker/docker-compose-dev.yml up -d
            echo ""
            echo "✅ Services started!"
            echo "   - API (with mock LLM): http://localhost:8080"
            echo "   - GUI (dev mode): http://localhost:3000"
            echo ""
            echo "To view logs:"
            echo "   docker-compose -f docker/docker-compose-dev.yml logs -f"
            echo ""
            echo "To stop services:"
            echo "   docker-compose -f docker/docker-compose-dev.yml down"
        fi
        ;;
    2)
        build_image "docker/Dockerfile" "ciris:latest"
        ;;
    3)
        build_image "docker/Dockerfile.optimized" "ciris:optimized"
        ;;
    4)
        build_image "docker/Dockerfile" "ciris:latest"
        build_image "docker/Dockerfile.optimized" "ciris:optimized"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# Only show general build complete message if not option 1
if [ "$choice" != "1" ]; then
    echo ""
    echo "Build complete! To run:"
    echo "  docker-compose -f docker/docker-compose-mock.yml up"
    echo ""
    echo "For Mac users experiencing issues:"
    echo "  - Try the optimized build (option 3) which creates a smaller image"
    echo "  - Ensure Docker Desktop has sufficient resources allocated"
    echo "  - Consider using the pre-built images from Docker Hub (coming soon)"
fi