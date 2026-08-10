# ============================================================
# Production Dockerfile — Multi-stage, < 500 MB, non-root
# ============================================================

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install into the system prefix; packages remain readable by the runtime user.
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Runtime
FROM python:3.11-slim AS runtime

RUN groupadd --system agent \
    && useradd --system --gid agent --home-dir /app --shell /usr/sbin/nologin agent

WORKDIR /app

# Copy ALL installed packages from builder (system-wide)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY app/ ./app/
COPY utils/ ./utils/

RUN chown -R agent:agent /app

USER agent

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" \
    || exit 1

CMD exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
