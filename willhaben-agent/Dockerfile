# Home Assistant provides BUILD_FROM via build.yaml; the default keeps a plain
# `docker build` / `docker compose build` working outside the Supervisor.
ARG BUILD_FROM=python:3.12-slim
FROM ${BUILD_FROM}

# System packages: curl for the healthcheck / OPEN WEB UI probe.
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Application code
COPY src/ /app/src/
COPY run.sh /run.sh
RUN chmod +x /run.sh

# /data is mounted and persisted by the Home Assistant Supervisor.
ENV DATA_DIR=/data \
    PORT=5000 \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

WORKDIR /app/src
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

CMD [ "/run.sh" ]
