# syntax=docker/dockerfile:1

# ---- builder: resolve deps with uv and build the venv -------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first so this layer is cached independently of app
# code changes (src/ edits won't invalidate the dependency install).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---- runtime: slim image with just the venv + source ---------------------
FROM python:3.13-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src

RUN useradd --create-home --uid 1000 penta \
    && chown -R penta:penta /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER penta

EXPOSE 8080

# The API (portal calls POST /documents/extract right after an upload) is
# the primary path. Run `docker run ... penta-ai-copilot python -m penta.poller`
# separately for the periodic-bucket-scan fallback.
CMD ["uvicorn", "penta.api:app", "--host", "0.0.0.0", "--port", "8080"]
