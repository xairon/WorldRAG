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


# ---- Runtime stage ----
FROM python:3.12-slim

WORKDIR /app

# Copy the virtual environment and source from the builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/backend backend/
COPY --from=builder /app/ontology ontology/
COPY --from=builder /app/scripts scripts/
COPY --from=builder /app/pyproject.toml pyproject.toml

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
