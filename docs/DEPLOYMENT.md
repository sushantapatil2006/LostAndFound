# Google Cloud Compute Engine Production Deployment Guide (Debian Linux)

This guide walks through deploying the Campus Lost & Found Portal to a Google Cloud Compute Engine VM running **Debian 12 (Bookworm)** or **Debian 13 (Trixie)**.

---

## 1. Architecture

The production environment consists of three isolated Docker containers orchestrated via `docker-compose.prod.yml`:

```
Internet (Port 80/443)
       │
       ▼
   ┌───────┐
   │ Caddy │ (Host HTTPS Reverse Proxy / Let's Encrypt TLS)
   └───┬───┘
       │
       ▼ (127.0.0.1:8080)
┌────────────────────────────────────────────────────────┐
│ Docker Host (Debian Linux)                             │
│                                                        │
│  ┌───────────────────────┐   ┌───────────────────────┐ │
│  │   frontend (Nginx)    │──▶│   api (Flask/Gunicorn)│ │
│  │   127.0.0.1:8080:80   │   │   Port 5000 (Internal)│ │
│  └───────────────────────┘   └───────────┬───────────┘ │
│                                          │             │
│                              ┌───────────▼───────────┐ │
│                              │      mysql:8.4        │ │
│                              │   Port 3306 (Internal)│ │
│                              └───────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

* **Network Isolation**: The Flask API (`port 5000`) and MySQL (`port 3306`) are strictly private to the internal Docker bridge network (`prod-internal-net`). They are never exposed to the public internet.
* **Frontend**: Nginx binds to host `127.0.0.1:8080:80`. Public internet traffic reaches it exclusively through Caddy over HTTPS.
* **Persistence**: Named volume `mysql-data` persists database state across image updates and container restarts.
* **Deployment Model**: Minimal-downtime container update (containers recreate in ~2-5 seconds; persistent volumes remain attached).

---

## 2. Infrastructure Prerequisites

1. **Google Cloud Project**: Active GCP project with billing enabled.
2. **Compute Engine VM**:
   * **OS**: Debian GNU/Linux 12 (Bookworm) or Debian 13 (Trixie)
   * **Machine Type**: `e2-standard-2` or `e2-medium` (Minimum 4 GB RAM recommended)
   * **Boot Disk**: Standard Persistent Disk (20 GB+)
   * **Networking**: External static IP address assigned
3. **Firewall Rules**:
   Allow ingress traffic on ports 80 and 443 from `0.0.0.0/0`:
   ```bash
   gcloud compute firewall-rules create allow-http-https \
       --direction=INGRESS \
       --priority=1000 \
       --network=default \
       --action=ALLOW \
       --rules=tcp:80,tcp:443 \
       --source-ranges=0.0.0.0/0 \
       --target-tags=http-server,https-server
   ```
   Add the network tags `http-server` and `https-server` to your VM instance.

---

## 3. Automated VM Setup

Connect to your Debian VM via SSH:
```bash
gcloud compute ssh <VM_NAME> --zone=<ZONE> --tunnel-through-iap
```

Clone the repository and execute the idempotent Debian setup script:
```bash
git clone https://github.com/sushantapatil2006/LostAndFound.git /opt/lostandfound
cd /opt/lostandfound
chmod +x scripts/*.sh

# Run the idempotent host preparation script
sudo ./scripts/setup-vm.sh
```

The script:
* Configures Docker's official Debian repository (without modifying existing Docker configurations or disk layouts).
* Installs `docker-ce`, `docker-ce-cli`, `containerd.io`, and `docker-compose-plugin`.
* Installs `caddy` from the official Debian repository.
* Configures deployment directories and permissions.

---

## 4. Production Configuration (`.env`)

Create your production environment file at `/opt/lostandfound/.env`:
```bash
cp .env.example .env
nano .env
```

Ensure the following variables are customized:
1. `SECRET_KEY`: Generate a secure 32-byte string:
   ```bash
   openssl rand -hex 32
   ```
2. `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`: Generate strong alphanumeric passwords:
   ```bash
   openssl rand -base64 24
   ```
3. `ADMIN_BOOTSTRAP_TOKEN`: Generate a private token for initial admin setup.
4. `GCS_BUCKET` & `GCP_PROJECT_ID`: If using Google Cloud Storage for uploaded photos.

Secure file permissions:
```bash
chmod 600 /opt/lostandfound/.env
```

---

## 5. Google Cloud Workload Identity Federation Setup

To allow GitHub Actions to deploy without long-lived JSON service account keys, configure Workload Identity Federation:

### Step 1: Create a Service Account for Deployment
```bash
gcloud iam service-accounts create github-deployer \
    --description="Deployment Service Account for GitHub Actions" \
    --display-name="GitHub Deployer"
```

### Step 2: Grant Minimum Required Roles
```bash
PROJECT_ID="$(gcloud config get-value project)"

# Grant Compute Instance Admin and IAP Tunneling
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:github-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/compute.instanceAdmin.v1"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:github-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iap.tunnelResourceAccessor"
```

### Step 3: Create Workload Identity Pool and Provider
```bash
gcloud iam workload-identity-pools create "github-actions-pool" \
    --location="global" \
    --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
    --location="global" \
    --workload-identity-pool="github-actions-pool" \
    --display-name="GitHub Actions Provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='sushantapatil2006/LostAndFound'"
```

### Step 4: Allow GitHub Actions to Impersonate the Service Account
```bash
POOL_ID="$(gcloud iam workload-identity-pools describe github-actions-pool --location=global --format='value(name)')"

gcloud iam service-accounts add-iam-policy-binding \
    "github-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/sushantapatil2006/LostAndFound"
```

Retrieve the provider resource path to set in GitHub Variables:
```bash
gcloud iam workload-identity-pools providers describe github-provider \
    --location=global \
    --workload-identity-pool=github-actions-pool \
    --format='value(name)'
```

---

## 6. First Production Deployment

Before automated continuous deployment triggers on pushes, perform an initial deployment on the VM using an immutable Git commit SHA (published to GHCR):

```bash
cd /opt/lostandfound

# Deploy specifying the immutable Git commit SHA published by CI
./scripts/deploy.sh <IMMUTABLE_GIT_COMMIT_SHA>
```

Verify that all three containers are healthy:
```bash
docker compose -f docker-compose.prod.yml ps
```
Output:
```
NAME                           IMAGE                                                STATUS                    PORTS
lostandfound-prod-api-1        ghcr.io/sushantapatil2006/lostandfound-backend:...   Up (healthy)              5000/tcp
lostandfound-prod-frontend-1   ghcr.io/sushantapatil2006/lostandfound-frontend:...  Up (healthy)              127.0.0.1:8080->80/tcp
lostandfound-prod-mysql-1      mysql:8.4                                            Up (healthy)              3306/tcp
```

### Bootstrap Initial Administrator
Run the Flask CLI command inside the running API container:
```bash
docker compose -f docker-compose.prod.yml exec -it api flask create-admin
```
Provide the admin Name, Email, and Password when prompted.

---

## 7. HTTPS Configuration (Caddy)

Edit `/etc/caddy/Caddyfile`:
```bash
sudo cp /opt/lostandfound/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile
```
Set your domain (e.g. `lostandfound.campus.edu`):
```caddy
lostandfound.campus.edu {
    reverse_proxy 127.0.0.1:8080 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto https
    }
}
```

Reload Caddy:
```bash
sudo systemctl reload caddy
```
Caddy will automatically provision and install a free SSL certificate from Let's Encrypt. Navigate to `https://lostandfound.campus.edu` in your browser.

---

## 8. Operations & Monitoring

* **Inspect live container logs**:
  ```bash
  docker compose -f docker-compose.prod.yml logs -f --tail=100
  ```
* **Inspect API logs specifically**:
  ```bash
  docker compose -f docker-compose.prod.yml logs -f api
  ```
* **Check service status**:
  ```bash
  docker compose -f docker-compose.prod.yml ps
  ```
* **Schedule Daily Backups**:
  Add to crontab (`crontab -e`):
  ```cron
  0 2 * * * /opt/lostandfound/scripts/backup-db.sh /opt/backups >> /var/log/db_backup.log 2>&1
  ```
