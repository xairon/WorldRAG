# ---- Build stage: install dependencies with uv ----
FROM python:3.12-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies first (layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY backend/ backend/
COPY ontology/ ontology/
COPY scripts/ scripts/

# Install the project itself
RUN uv sync --frozen --no-dev


# ── Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r worldrag && useradd -r -g worldrag -d /app worldrag

WORKDIR /app

COPY --from=builder --chown=worldrag:worldrag /app/.venv .venv
COPY --chown=worldrag:worldrag backend/ backend/
COPY --chown=worldrag:worldrag ontology/ ontology/
COPY --chown=worldrag:worldrag scripts/ scripts/
COPY --chown=worldrag:worldrag pyproject.toml .

ENV PATH="/app/.venv/bin:$PATH"

USER worldrag
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
