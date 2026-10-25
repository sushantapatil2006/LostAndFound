#!/usr/bin/env bash
# ==============================================================================
# Production Deployment & Rollback Script for Campus Lost & Found Portal
# ==============================================================================
# Usage:
#   ./scripts/deploy.sh <IMMUTABLE_GIT_COMMIT_SHA>
#
# Requirements:
#   - TARGET_RELEASE must be an immutable Git commit SHA (7-40 hex chars).
#   - Mutable tags such as 'latest' are explicitly rejected in production.
#   - Preserves persistent volumes (mysql-data) throughout deployment & rollback.
# ==============================================================================
set -euo pipefail

TARGET_RELEASE="${1:-}"

# 1. Enforce immutable Git commit SHA (reject empty or 'latest')
if [ -z "$TARGET_RELEASE" ]; then
    echo "ERROR: Target release identifier (Git commit SHA) must be provided as the first argument."
    echo "Usage: ./scripts/deploy.sh <GIT_COMMIT_SHA>"
    exit 1
fi

if [ "$TARGET_RELEASE" = "latest" ]; then
    echo "ERROR: Refusing to deploy mutable tag 'latest' in production."
    echo "Production deployments must specify an immutable Git commit SHA (e.g., 7 to 40 hexadecimal characters)."
    exit 1
fi

if [[ ! "$TARGET_RELEASE" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
    echo "ERROR: Invalid release identifier '${TARGET_RELEASE}'."
    echo "Expected an immutable Git commit SHA (7 to 40 hexadecimal characters)."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$APP_DIR"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"
CURRENT_RELEASE_FILE=".current_release"
PREVIOUS_RELEASE_FILE=".previous_release"

echo "=========================================================="
echo " Deploying Lost & Found Portal Release: ${TARGET_RELEASE}"
echo " Mode: Minimal-downtime container recreation"
echo "=========================================================="

# 2. Verify environment configuration file
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Missing ${ENV_FILE} configuration file in ${APP_DIR}."
    echo "Please create ${ENV_FILE} based on .env.example before deploying."
    exit 1
fi

# Load environment variables
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Ensure critical secrets are configured
if [ -z "${SECRET_KEY:-}" ] || [ "$SECRET_KEY" = "change-this-to-a-very-secure-random-32-byte-hex-string" ]; then
    echo "ERROR: Production SECRET_KEY is missing or using default placeholder in ${ENV_FILE}."
    exit 1
fi

if [ -z "${MYSQL_PASSWORD:-}" ] || [ -z "${MYSQL_ROOT_PASSWORD:-}" ]; then
    echo "ERROR: MYSQL_PASSWORD and MYSQL_ROOT_PASSWORD must be configured in ${ENV_FILE}."
    exit 1
fi

# 3. Record rollback reference before performing changes
if [ -f "$CURRENT_RELEASE_FILE" ]; then
    CURRENT_VERSION="$(cat "$CURRENT_RELEASE_FILE")"
    if [ "$CURRENT_VERSION" != "$TARGET_RELEASE" ]; then
        echo "$CURRENT_VERSION" > "$PREVIOUS_RELEASE_FILE"
        echo "--> Recorded current release (${CURRENT_VERSION}) as rollback target."
    fi
fi

# 4. Pull target release images from GHCR
export IMAGE_TAG="$TARGET_RELEASE"
echo "--> Pulling release images for immutable tag ${IMAGE_TAG}..."
if ! docker compose -f "$COMPOSE_FILE" pull frontend api; then
    echo "ERROR: Failed to pull images for tag ${IMAGE_TAG} from container registry."
    exit 1
fi

# 5. Recreate application services (brief container transition)
echo "--> Recreating application services..."
if ! docker compose -f "$COMPOSE_FILE" up -d --remove-orphans; then
    echo "ERROR: Docker Compose failed to launch services."
    exit 1
fi

# 6. Verify container health checks
echo "--> Verifying application health endpoints..."
HEALTHY=false
RETRIES=15
WAIT_SECONDS=3

for i in $(seq 1 $RETRIES); do
    echo "    Health verification attempt ${i}/${RETRIES}..."
    sleep $WAIT_SECONDS

    # Verify frontend health
    FRONTEND_STATUS="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/healthz || true)"
    # Verify API health through frontend reverse proxy
    API_STATUS="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/api/health || true)"

    if [ "$FRONTEND_STATUS" = "200" ] && [ "$API_STATUS" = "200" ]; then
        HEALTHY=true
        break
    fi
done

if [ "$HEALTHY" = true ]; then
    echo "=========================================================="
    echo " Deployment Succeeded! Release: ${TARGET_RELEASE}"
    echo " Frontend & API health endpoints verified (200 OK)."
    echo "=========================================================="
    echo "$TARGET_RELEASE" > "$CURRENT_RELEASE_FILE"
    exit 0
else
    echo "=========================================================="
    echo " CRITICAL: Health checks failed after ${RETRIES} attempts!"
    echo " Frontend HTTP status: ${FRONTEND_STATUS:-unknown}"
    echo " API HTTP status: ${API_STATUS:-unknown}"
    echo " Fetching recent container logs for diagnosis..."
    docker compose -f "$COMPOSE_FILE" logs --tail 50
    echo "=========================================================="

    # 7. Safe Automated Rollback to previous immutable release
    if [ -f "$PREVIOUS_RELEASE_FILE" ]; then
        ROLLBACK_TARGET="$(cat "$PREVIOUS_RELEASE_FILE")"
        echo "--> Initiating automated rollback to previous release: ${ROLLBACK_TARGET}..."
        export IMAGE_TAG="$ROLLBACK_TARGET"
        docker compose -f "$COMPOSE_FILE" pull frontend api || true
        docker compose -f "$COMPOSE_FILE" up -d --remove-orphans || true
        echo "--> Rollback dispatched. Persistent database volume was preserved."
    else
        echo "--> No previous release recorded. Leaving containers in current state for inspection."
    fi

    exit 1
fi
