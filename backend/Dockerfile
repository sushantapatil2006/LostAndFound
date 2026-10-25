FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GUNICORN_WORKERS=2

WORKDIR /app

# Install compilation dependencies for mysqlclient and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create an unprivileged application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy application source code
COPY . .

# Ensure upload directory exists and has correct ownership
RUN mkdir -p uploads/items && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

CMD ["sh", "-c", "gunicorn --workers ${GUNICORN_WORKERS:-2} --threads 4 --bind 0.0.0.0:5000 --access-logfile - --error-logfile - app:app"]
