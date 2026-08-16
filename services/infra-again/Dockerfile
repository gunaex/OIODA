# INFRA-AGAIN Backend Dockerfile — Fly.io Deployment
FROM python:3.11-slim

WORKDIR /app

# Install system deps + OpenTofu
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg \
    && curl -fsSL https://get.opentofu.org/install-opentofu.sh -o /tmp/install-opentofu.sh \
    && sh /tmp/install-opentofu.sh --install-method standalone 2>/dev/null || true \
    && (command -v tofu >/dev/null 2>&1 || \
        (curl -fsSL https://github.com/opentofu/opentofu/releases/download/v1.9.0/tofu_1.9.0_linux_amd64.zip -o /tmp/tofu.zip \
         && apt-get install -y --no-install-recommends unzip \
         && unzip -o /tmp/tofu.zip -d /usr/local/bin/ \
         && chmod +x /usr/local/bin/tofu)) \
    && rm -rf /var/lib/apt/lists/* /tmp/*.zip /tmp/install-opentofu.sh || true

# Install Python deps
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir fastapi uvicorn pydantic httpx boto3 pyyaml

# Create data directory
RUN mkdir -p /data

EXPOSE 8080

CMD ["uvicorn", "infra_again.api:app", "--host", "0.0.0.0", "--port", "8080"]
