FROM python:3.12.10-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/workspace/.venv

WORKDIR /workspace

COPY . .
RUN uv sync --locked --no-dev --package nordic-regulated-ai-agent-platform-api


FROM python:3.12.10-slim-bookworm AS runtime

ENV PATH="/workspace/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get upgrade --yes && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --gid 10001 app && \
    useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /workspace

COPY --from=builder --chown=app:app /workspace/.venv /workspace/.venv
COPY --from=builder --chown=app:app /workspace/apps/api/src /workspace/apps/api/src
COPY --from=builder --chown=app:app /workspace/services/agent_orchestrator/src /workspace/services/agent_orchestrator/src
COPY --from=builder --chown=app:app /workspace/services/evaluation/src /workspace/services/evaluation/src

USER app

CMD ["celery", "--quiet", "-A", "app.workers.celery_app:celery_app", "worker", "-Q", "document-parser,document-indexer,agent-orchestrator,evaluation", "--beat", "--schedule", "/tmp/celerybeat-schedule", "--loglevel=WARNING"]
