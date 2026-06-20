# Local-development image only. Production hardening and release images belong to Phase 32.
FROM node:24.17.0-bookworm-slim

ENV PNPM_HOME="/pnpm" \
    PATH="/pnpm:$PATH"

RUN corepack enable && corepack prepare pnpm@11.8.0 --activate

WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @nordic-regulated-ai-agent-platform/web

COPY apps/web ./apps/web

EXPOSE 3000

CMD ["pnpm", "--filter", "@nordic-regulated-ai-agent-platform/web", "dev"]
