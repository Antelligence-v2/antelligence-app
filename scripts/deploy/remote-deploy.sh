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

docker run -d \
  --name "$NAME" \
  --restart unless-stopped \
  -p "${PORT}:${PORT}" \
  --env-file "$ENV_FILE" \
  "$IMAGE" > /dev/null

echo "Waiting up to ${HEALTH_TIMEOUT}s for /health"
for _ in $(seq 1 $((HEALTH_TIMEOUT / 5))); do
  if healthy; then
    echo "Healthy: ${IMAGE}"
    if $had_prev; then docker rm "${NAME}-prev" > /dev/null; fi
    docker image prune -af > /dev/null
    exit 0
  fi
  sleep 5
done

echo "New container never became healthy; last logs:"
docker logs --tail 50 "$NAME" || true
docker rm -f "$NAME" > /dev/null
if $had_prev; then
  echo "Rolling back to previous container"
  docker rename "${NAME}-prev" "$NAME"
  docker start "$NAME" > /dev/null
fi
exit 1
