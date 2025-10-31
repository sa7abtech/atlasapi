FROM python:3.11-slim

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set Python path so imports work
ENV PYTHONPATH=/app

# Make start script executable
RUN chmod +x railway_start.sh

# Expose port (Railway will set PORT env var)
EXPOSE ${PORT:-8000}

# Start both API and bot
CMD ["./railway_start.sh"]
