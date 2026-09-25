# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

FROM deps AS development
RUN pip install -e ".[dev]"
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM deps AS production
COPY app ./app
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p \
        /home/appuser/uploads/products \
        /home/appuser/uploads/categories \
        /home/appuser/uploads/businesses \
        /home/appuser/uploads/verification \
        /home/appuser/uploads/delivery-evidence \
        /home/appuser/uploads/ai-sourcing \
    && chown -R appuser:appuser /home/appuser/uploads
USER appuser
ENV PORT=8000 \
    UPLOAD_ROOT=/home/appuser/uploads
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || exit 1
# Render injects $PORT — bind to it so the platform health check succeeds.
# Only Render's proxy can reach the container, so its X-Forwarded-For is trusted;
# without this every request appears to come from the proxy IP.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 30"]
