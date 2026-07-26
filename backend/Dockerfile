# syntax=docker/dockerfile:1

# Multi-stage: dependencies are resolved once in the builder and only the
# installed packages are copied forward, so build tools never reach the runtime
# image.
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app

RUN pip install --prefix=/install .

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

# Runs as a non-root user: a container process that does not need root should
# never have it, and a mounted volume is the one thing this app writes to.
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=appuser:appuser . .

# The SQLite database and uploads live here, mounted as a persistent volume in
# production. Without a volume the data disappears on every redeploy.
RUN mkdir -p /app/var/uploads && chown -R appuser:appuser /app/var

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"

# One worker, deliberately. Presence and the WebSocket connection registry are
# in-process, so a second worker would hold a different set of connections and
# silently fail to deliver to half of them. Scaling out needs the Redis-backed
# ConnectionManager described in PROJECT.md before the worker count goes up.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
