# The worker shares the locked health-only API runtime in Phase 2. It does not consume jobs yet.
FROM python:3.12.10-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/workspace/.venv/bin:$PATH"

WORKDIR /workspace

COPY . .
RUN uv sync --locked --no-dev --package nordic-regulated-ai-agent-platform-api

EXPOSE 8001

CMD ["uvicorn", "app.workers.readiness:app", "--host", "0.0.0.0", "--port", "8001"]
