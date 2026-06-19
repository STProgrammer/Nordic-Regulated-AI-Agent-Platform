# Local-development image only. Production hardening and release images belong to Phase 32.
FROM python:3.12.10-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/workspace/.venv/bin:$PATH"

WORKDIR /workspace

# The repository root is copied intentionally: uv needs the workspace manifests and uv.lock to
# install the API package from the locked workspace without relying on network resolution at run time.
COPY . .
RUN uv sync --locked --no-dev --package nordic-regulated-ai-agent-platform-api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
