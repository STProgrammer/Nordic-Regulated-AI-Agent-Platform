#!/usr/bin/env bash

set -euo pipefail

compose=(
  docker compose
  --env-file infra/docker/production-local.env.example
  -f docker-compose.production.yml
)

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans
}

trap cleanup EXIT

"${compose[@]}" config --quiet
"${compose[@]}" build --quiet web api worker
"${compose[@]}" up --wait --detach web api worker postgres redis azurite
"${compose[@]}" up --detach azurite-init

azurite_init_id="$("${compose[@]}" ps -aq azurite-init)"
for _ in $(seq 1 30); do
  azurite_init_status="$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' "$azurite_init_id")"
  if [[ "$azurite_init_status" == 'exited:0' ]]; then
    break
  fi
  sleep 1
done
[[ "$azurite_init_status" == 'exited:0' ]]

"${compose[@]}" exec -T api alembic -c apps/api/alembic.ini upgrade head
"${compose[@]}" exec -T api python scripts/check_migrations.py
"${compose[@]}" exec -T worker sh -ec \
  'celery -A app.workers.celery_app:celery_app inspect ping -d "celery@$HOSTNAME" --timeout 2 | grep -q pong'

web_address="$("${compose[@]}" port web 3000 | head -n 1)"
api_address="$("${compose[@]}" port api 8000 | head -n 1)"
[[ "$web_address" == 127.0.0.1:* ]]
[[ "$api_address" == 127.0.0.1:* ]]

curl --fail --silent --show-error "http://${web_address}/nb/login" | grep -q 'nordic-app-shell'
curl --fail --silent --show-error "http://${api_address}/health/live" | grep -q '"status":"alive"'
curl --fail --silent --show-error "http://${api_address}/health/ready" | grep -q '"status":"ready"'

proxy_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "http://${web_address}/api/auth/me")"
[[ "$proxy_status" == '401' ]]

for service in api web worker; do
  image_id="$("${compose[@]}" images -q "$service")"
  [[ "$(docker image inspect --format '{{.Config.User}}' "$image_id")" == 'app' ]]
done

printf 'Production release validation passed.\n'
