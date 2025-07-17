FROM python:3.12-slim

# Install dependencies including build tools for psutil
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
# Try to use pre-compiled wheels first, fall back to building from source
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy the rest of the application code
COPY . .

# Default command - will be overridden by docker-compose
CMD ["python", "main.py"]