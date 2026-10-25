#!/usr/bin/env bash
# ==============================================================================
# Setup Script for Google Cloud Compute Engine VM (Debian 12 / 13)
# ==============================================================================
# Target OS: Debian GNU/Linux 12 (Bookworm) / Debian GNU/Linux 13 (Trixie)
#
# Idempotent host preparation:
# 1. Installs official Docker Engine & Docker Compose plugin from Docker's Debian APT repository
# 2. Installs Caddy web server from official Debian repository for automated HTTPS TLS
# 3. Configures deployment user group memberships and application directories
# 4. Preserves all existing Docker configurations, data-root, and disk partitions
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo " Starting Lost & Found Portal VM Initialization (Debian)"
echo "=========================================================="

# Determine sudo requirement
if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    if ! command -v sudo &> /dev/null; then
        echo "ERROR: 'sudo' command is required when running as non-root."
        exit 1
    fi
    SUDO="sudo"
fi

APP_DIR="/opt/lostandfound"
BACKUP_DIR="/opt/backups"
DEPLOY_USER="${SUDO_USER:-$USER}"

# Verify operating system is Debian
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "${ID:-}" != "debian" ] && [ "${ID_LIKE:-}" != *"debian"* ]; then
        echo "WARNING: Detected OS is '${ID:-unknown}'. This script is tailored for Debian 12 (Bookworm) / 13 (Trixie)."
    fi
    echo "--> Running on: ${PRETTY_NAME:-Debian}"
fi

# 1. Update APT index and install essential prerequisite utilities
echo "--> Installing prerequisite utilities..."
$SUDO apt-get update -y
$SUDO apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    jq \
    apt-transport-https

# 2. Install Docker Engine and Docker Compose Plugin (Official Docker Debian Repository)
# Preserves existing installations and avoids touching existing daemon.json or disk layouts
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo "--> Docker Engine and Compose plugin already installed:"
    docker --version
    docker compose version
else
    echo "--> Installing official Docker Engine for Debian..."
    $SUDO install -m 0755 -d /etc/apt/keyrings
    $SUDO curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    $SUDO chmod a+r /etc/apt/keyrings/docker.asc

    DEBIAN_CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
      ${DEBIAN_CODENAME} stable" | \
      $SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null

    $SUDO apt-get update -y
    $SUDO apt-get install -y \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin
fi

# Enable and start Docker daemon safely (does NOT alter existing /etc/docker/daemon.json or data-root)
$SUDO systemctl enable docker
$SUDO systemctl start docker

# Add deployment user to docker group if not already present
if ! groups "$DEPLOY_USER" 2>/dev/null | grep -q '\bdocker\b'; then
    echo "--> Adding user '$DEPLOY_USER' to docker group..."
    $SUDO usermod -aG docker "$DEPLOY_USER"
    echo "    (Note: Log out and log back in for docker group membership to take effect)"
fi

# 3. Install Caddy Web Server (Official Caddy Debian Repository)
if command -v caddy &> /dev/null; then
    echo "--> Caddy already installed: $(caddy version)"
else
    echo "--> Installing Caddy web server from official Debian repository..."
    $SUDO apt-get install -y debian-keyring debian-archive-keyring
    curl -1sLF 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | $SUDO gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLF 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | $SUDO tee /etc/apt/sources.list.d/caddy-stable.list
    $SUDO apt-get update -y
    $SUDO apt-get install -y caddy
fi

# 4. Prepare application and backup directories (Idempotent)
echo "--> Preparing application and backup directories..."
$SUDO mkdir -p "$APP_DIR"
$SUDO mkdir -p "$BACKUP_DIR"

if [ -n "$DEPLOY_USER" ] && id "$DEPLOY_USER" &>/dev/null; then
    $SUDO chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$APP_DIR"
    $SUDO chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$BACKUP_DIR"
fi
$SUDO chmod 750 "$APP_DIR"
$SUDO chmod 700 "$BACKUP_DIR"

# 5. Note on Networking & Firewall
echo "=========================================================="
echo " VM Setup Complete for Debian!"
echo " Ingress Traffic Note:"
echo "   In Google Cloud, ingress ports 80 (HTTP) and 443 (HTTPS)"
echo "   are governed by VPC Firewall rules attached to this VM."
echo "   Ensure network tags 'http-server' and 'https-server' are applied."
echo "   Ports 8080, 5000, and 3306 remain blocked from public internet."
echo "=========================================================="
echo " Next steps for initial release:"
echo " 1. Clone repository into $APP_DIR"
echo " 2. Copy .env.example to $APP_DIR/.env and set strong secrets"
echo " 3. Copy Caddyfile to /etc/caddy/Caddyfile and configure domain"
echo " 4. Run: ./scripts/deploy.sh <IMMUTABLE_GIT_COMMIT_SHA>"
echo "=========================================================="
