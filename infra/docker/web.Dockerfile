FROM node:24.17.0-bookworm-slim AS dependencies

ENV PNPM_HOME="/pnpm" \
    PATH="/pnpm:$PATH"

RUN corepack enable && corepack prepare pnpm@11.8.0 --activate

WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @nordic-regulated-ai-agent-platform/web


FROM dependencies AS builder

COPY apps/web ./apps/web

# Production headers are compiled into the release image. API_ORIGIN is not a
# build argument: the route handler resolves it only when a request arrives.
ENV NORDIC_WEB_ENVIRONMENT=production
RUN pnpm --filter @nordic-regulated-ai-agent-platform/web build


FROM node:24.17.0-bookworm-slim AS runtime

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# npm is needed only in the build stage. Removing it keeps the runtime image
# smaller and avoids shipping an unused package manager.
RUN apt-get update && \
    apt-get upgrade --yes && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/local/lib/node_modules/npm && \
    groupadd --gid 10001 app && \
    useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /workspace

COPY --from=builder --chown=app:app /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=app:app /workspace/apps/web/.next/static ./apps/web/.next/static

USER app

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
