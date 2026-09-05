# Small Business Deployment Starter demo image.
# Standard library only: no pip installs are needed at build or run time.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    MODE=stateless \
    DATA_DIR=/data

WORKDIR /srv/app

COPY VERSION .
COPY app ./app
COPY scripts ./scripts

# /data is a mount point for explicitly selected local durable mode.
# Writability does not establish persistence across container replacement.
RUN mkdir -p /data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python3", "scripts/healthcheck.py"]

# Cloud platforms (ECS, Cloud Run, Container Apps) send /health probes on
# PORT 8080; healthcheck.py reuses the same contract inside the container.
CMD ["python3", "-m", "app.server"]
