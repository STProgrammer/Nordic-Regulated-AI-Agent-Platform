# The worker shares the API runtime and consumes private parser/index queues.
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

CMD ["celery", "--quiet", "-A", "app.workers.celery_app:celery_app", "worker", "-Q", "document-parser,document-indexer", "--beat", "--loglevel=WARNING"]
