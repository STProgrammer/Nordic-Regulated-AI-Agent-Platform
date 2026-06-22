FROM python:3.12.10-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/workspace/.venv

WORKDIR /workspace

# uv resolves the locked workspace as one unit. Tests and build tooling remain
# in this stage and are deliberately absent from the runtime image.
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
COPY --from=builder --chown=app:app /workspace/apps/api/alembic.ini /workspace/apps/api/alembic.ini
COPY --from=builder --chown=app:app /workspace/apps/api/migrations /workspace/apps/api/migrations
COPY --from=builder --chown=app:app /workspace/apps/api/src /workspace/apps/api/src
COPY --from=builder --chown=app:app /workspace/services/agent_orchestrator/src /workspace/services/agent_orchestrator/src
COPY --from=builder --chown=app:app /workspace/services/evaluation/src /workspace/services/evaluation/src
COPY --from=builder --chown=app:app /workspace/scripts/check_migrations.py /workspace/scripts/check_migrations.py

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
