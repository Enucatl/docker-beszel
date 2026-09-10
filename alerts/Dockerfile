FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
RUN uv sync --no-dev

ENTRYPOINT ["/app/.venv/bin/alerts-init"]
