#!/usr/bin/env bash

# Verify the already-running local stack without adding business data or changing service state.
set -euo pipefail

compose_env_file="${COMPOSE_ENV_FILE:-}"
if [[ -z "$compose_env_file" ]]; then
  if [[ -f .env ]]; then
    compose_env_file=".env"
  else
    compose_env_file=".env.example"
  fi
fi

if [[ ! -f "$compose_env_file" ]]; then
  printf 'Compose environment file not found: %s\n' "$compose_env_file" >&2
  exit 1
fi

compose=(docker compose --env-file "$compose_env_file")
required_services=(web api worker postgres redis azurite)

service_health() {
  local service="$1"
  local container_id
  container_id="$("${compose[@]}" ps -q "$service")"

  if [[ -z "$container_id" ]]; then
    return 1
  fi

  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
    "$container_id"
}

wait_for_healthy_service() {
  local service="$1"
  local attempt
  local current_health

  for attempt in $(seq 1 30); do
    current_health="$(service_health "$service" 2>/dev/null || true)"
    if [[ "$current_health" == "healthy" ]]; then
      return 0
    fi
    sleep 2
  done

  printf 'Service %s did not become healthy within 60 seconds.\n' "$service" >&2
  return 1
}

compose_port() {
  local service="$1"
  local container_port="$2"
  local published_port

  published_port="$("${compose[@]}" port "$service" "$container_port" | head -n 1)"
  if [[ -z "$published_port" ]]; then
    printf 'No published port found for %s:%s.\n' "$service" "$container_port" >&2
    return 1
  fi
  printf '%s' "$published_port"
}

check_http() {
  local url="$1"
  local expected_text="$2"

  python3 - "$url" "$expected_text" <<'PY'
import sys
import urllib.request

url, expected_text = sys.argv[1:]
with urllib.request.urlopen(url, timeout=5) as response:
    body = response.read().decode("utf-8")

if response.status != 200:
    raise SystemExit(f"Expected HTTP 200 from {url}, received {response.status}.")
if expected_text not in body:
    raise SystemExit(f"Expected response from {url} to contain the local health contract.")
PY
}

check_azurite_blob() {
  local url="$1"

  python3 - "$url" <<'PY'
import sys
import urllib.error
import urllib.request

url = sys.argv[1]
try:
    urllib.request.urlopen(url, timeout=5)
except urllib.error.HTTPError as error:
    if error.code >= 500:
        raise SystemExit(f"Azurite returned HTTP {error.code} from {url}.")
except Exception as error:
    raise SystemExit(f"Azurite blob endpoint not reachable at {url}: {error}")
PY
}

assert_loopback_binding() {
  local service="$1"
  local address="$2"

  if [[ "$address" != 127.0.0.1:* ]]; then
    printf 'Service %s is not bound to loopback only: %s\n' "$service" "$address" >&2
    return 1
  fi
}

for service in "${required_services[@]}"; do
  wait_for_healthy_service "$service"
done

azurite_init_id="$("${compose[@]}" ps -aq azurite-init)"
if [[ -z "$azurite_init_id" ]]; then
  printf 'azurite-init container was not provisioned.\n' >&2
  exit 1
fi

azurite_init_status="$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' "$azurite_init_id")"
if [[ "$azurite_init_status" != "exited:0" ]]; then
  printf 'azurite-init did not finish successfully (status %s).\n' "$azurite_init_status" >&2
  exit 1
fi

web_address="$(compose_port web 3000)"
api_address="$(compose_port api 8000)"
azurite_address="$(compose_port azurite 10000)"
postgres_address="$(compose_port postgres 5432)"
redis_address="$(compose_port redis 6379)"

assert_loopback_binding web "$web_address"
assert_loopback_binding api "$api_address"
assert_loopback_binding azurite "$azurite_address"
assert_loopback_binding postgres "$postgres_address"
assert_loopback_binding redis "$redis_address"

check_http "http://${web_address}/" "nordic-app-shell"
check_http "http://${api_address}/health/live" '"status":"alive"'
check_http "http://${api_address}/health/ready" '"status":"ready"'
check_http "http://${api_address}/openapi.json" '"openapi"'
check_http "http://${api_address}/docs" "Swagger UI"
check_azurite_blob "http://${azurite_address}/devstoreaccount1"

"${compose[@]}" exec -T postgres sh -ec 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null'
"${compose[@]}" exec -T postgres sh -ec \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_available_extensions WHERE name = '\''vector'\''" | grep -qx 1'
"${compose[@]}" exec -T redis redis-cli ping | grep -qx PONG
"${compose[@]}" run --rm --no-deps --entrypoint /bin/sh azurite-init -ec \
  'az storage container show --name "$AZURITE_CONTAINER" --connection-string "DefaultEndpointsProtocol=http;AccountName=$AZURITE_ACCOUNT_NAME;AccountKey=$AZURITE_ACCOUNT_KEY;BlobEndpoint=$AZURITE_BLOB_ENDPOINT;" >/dev/null'

printf 'Local stack verification passed.\n'
