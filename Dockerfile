FROM python:3.9-slim

WORKDIR /app

# Install system dependencies untuk ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/health', timeout=5)" || exit 1

# Run application
CMD ["python", "app.py"]
