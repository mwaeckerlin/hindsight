#!/usr/bin/env bash
# End to end: starts the built image in tests/e2e/docker-compose.yml without
# internet access, stores a memory, restarts the service, recalls the memory,
# and checks that the tenant key reaches the container as a file only.
#
# Usage: tests/run-e2e.sh   (after `npm run build`)

set -uo pipefail
cd "$(dirname "$0")/e2e"

export HINDSIGHT_E2E_TENANT_KEY="e2e-tenant-key-of-the-test-stack"
COMPOSE=(docker compose -f docker-compose.yml)
FAIL=0

cleanup() { "${COMPOSE[@]}" down -v --remove-orphans > /dev/null 2>&1; }
trap cleanup EXIT
cleanup

wait_healthy() {
    local service="${1:-hindsight}" id
    id=$("${COMPOSE[@]}" ps -q "${service}")
    for _ in $(seq 1 120); do
        case "$(docker inspect --format '{{.State.Health.Status}}' "${id}" 2>/dev/null)" in
            healthy) return 0 ;;
            unhealthy) break ;;
        esac
        sleep 5
    done
    echo "  FAIL  ${service}_becomes_healthy: $(docker inspect --format '{{.State.Health.Status}}' "${id}")"
    "${COMPOSE[@]}" logs --tail 80 "${service}"
    return 1
}

echo "==> Hindsight end to end"
"${COMPOSE[@]}" build check || exit 1
"${COMPOSE[@]}" up -d hindsight || exit 1
wait_healthy || exit 1
echo "  PASS  hindsight_becomes_healthy_without_internet"

"${COMPOSE[@]}" run --rm check store || FAIL=1

# the key is a file under /run/secrets, never a value in the environment
ENV=$(docker inspect --format '{{join .Config.Env "\n"}}' "$("${COMPOSE[@]}" ps -q hindsight)")
if grep -q "${HINDSIGHT_E2E_TENANT_KEY}" <<< "${ENV}"; then
    echo "  FAIL  tenant_key_not_in_environment: the key stands in the container environment"
    FAIL=1
else
    echo "  PASS  tenant_key_not_in_environment"
fi

"${COMPOSE[@]}" restart hindsight || exit 1
wait_healthy || exit 1
"${COMPOSE[@]}" run --rm check restored || FAIL=1

# the key is optional: without it the service runs open
"${COMPOSE[@]}" up -d hindsight-open || exit 1
wait_healthy hindsight-open || exit 1
"${COMPOSE[@]}" run --rm -e HINDSIGHT_URL=http://hindsight-open:8888 check open || FAIL=1

if [[ ${FAIL} -ne 0 ]]; then
    "${COMPOSE[@]}" logs --tail 80 hindsight
    exit 1
fi
echo "==> Hindsight end to end: green"
