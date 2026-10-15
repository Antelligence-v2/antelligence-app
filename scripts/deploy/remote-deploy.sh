#!/bin/bash
# Swap the running prod container to a new image, rolling back if it never turns healthy.
# Runs on the EC2 host, piped over SSH by .github/workflows/deploy.yml:
#   ssh host 'bash -s' -- <image> < scripts/deploy/remote-deploy.sh
# The image must already be pullable (the workflow logs the host into GHCR first).

set -euo pipefail

IMAGE="${1:?usage: remote-deploy.sh <image>}"
NAME=antelligence
PORT=8001
ENV_FILE="$HOME/.env"
HEALTH_TIMEOUT=120

healthy() {
  curl -sf "http://localhost:${PORT}/health" > /dev/null
}

# The root disk is small; drop images no container uses before pulling.
docker image prune -af > /dev/null
echo "Pulling ${IMAGE}"
docker pull "$IMAGE"

had_prev=false
if docker inspect "$NAME" > /dev/null 2>&1; then
  had_prev=true
  echo "Stopping current container ($(docker inspect --format '{{.Config.Image}}' "$NAME"))"
  docker rm -f "${NAME}-prev" > /dev/null 2>&1 || true
  docker rename "$NAME" "${NAME}-prev"
  docker stop "${NAME}-prev" > /dev/null
fi

# From here on, any failure (docker run included) puts the previous container back.
restore() {
  local status=$?
  [ "$status" -eq 0 ] && return
  echo "Deploy failed; last logs:"
  docker logs --tail 50 "$NAME" 2>&1 || true
  docker rm -f "$NAME" > /dev/null 2>&1 || true
  if $had_prev; then
    echo "Rolling back to previous container"
    docker rename "${NAME}-prev" "$NAME"
    docker start "$NAME" > /dev/null
  fi
  exit "$status"
}
trap restore EXIT

# Runs, experiments and the simulation cache live in named volumes so they survive swaps.
docker run -d \
  --name "$NAME" \
  --restart unless-stopped \
  --log-opt max-size=10m --log-opt max-file=3 \
  -p "${PORT}:${PORT}" \
  --env-file "$ENV_FILE" \
  -v antelligence-data:/app/data \
  -v antelligence-cache:/app/simulation_cache \
  "$IMAGE" > /dev/null

echo "Waiting up to ${HEALTH_TIMEOUT}s for /health"
for _ in $(seq 1 $((HEALTH_TIMEOUT / 5))); do
  if healthy; then
    # Healthy is the point of no return: cleanup failures below must not roll back.
    trap - EXIT
    echo "Healthy: ${IMAGE}"
    if $had_prev; then docker rm "${NAME}-prev" > /dev/null || true; fi
    docker image prune -af > /dev/null || true
    exit 0
  fi
  sleep 5
done

echo "New container never became healthy"
exit 1
