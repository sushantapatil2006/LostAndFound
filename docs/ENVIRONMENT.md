# Environment Variables & Configuration Reference

This document provides a detailed reference for all configuration options across development and production environments.

---

## 1. Application Settings

| Variable | Environment | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENV` | All | `development` | Runtime environment (`development`, `testing`, `production`). In production, strict security validations are enforced. |
| `FLASK_DEBUG` | Dev | `0` | Enable Flask debug mode (`1` for dev, must be `0` in production). |
| `SECRET_KEY` | **Required in Prod** | `dev-only-change-me` | Cryptographic secret for signing JWT HS256 authentication tokens. Application will **fail to start** in production if this is unset or set to the development default. |
| `JWT_EXPIRY_HOURS` | All | `24` | Token validity duration in hours before users must log in again. |
| `GUNICORN_WORKERS` | Prod | `2` | Number of Gunicorn worker processes. Recommended: `2` to `4` for a 4GB RAM Compute Engine VM. |
| `NUM_PROXIES` | Prod | `1` | Number of reverse proxies in front of Flask (Nginx/Caddy) to handle `X-Forwarded-*` headers correctly. |

---

## 2. Administrator Bootstrap

| Variable | Environment | Description |
| :--- | :--- | :--- |
| `ADMIN_EMAILS` | All | Informational comma-separated list of administrative contact emails. (Registration with these emails does **not** grant automatic admin privileges). |
| `ADMIN_BOOTSTRAP_TOKEN` | Optional/Prod | Secret token used during initial provisioning. When supplied via HTTP header `X-Admin-Bootstrap-Token` during `/api/register` or `/api/admin/bootstrap`, grants admin status. |

---

## 3. Database Configuration

| Variable | Environment | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | Prod | *Dynamic* | SQLAlchemy database URI. Format: `mysql+mysqldb://${MYSQL_USER}:${MYSQL_PASSWORD}@mysql:3306/${MYSQL_DATABASE}` |
| `MYSQL_DATABASE` | Dev/Prod | `lost_found_portal` | Database name created on initialization. |
| `MYSQL_USER` | Dev/Prod | `lostfound` | Application MySQL database user. |
| `MYSQL_PASSWORD` | **Required in Prod** | `lostfound_secret` | Password for MySQL user. |
| `MYSQL_ROOT_PASSWORD`| **Required in Prod**| `root_secret` | MySQL administrative root password. |
| `DB_POOL_SIZE` | Prod | `10` | Maximum number of persistent connections in connection pool. |
| `DB_POOL_RECYCLE`| Prod | `280` | Connection recycle timeout in seconds (must be below MySQL wait_timeout). |
| `DB_MAX_OVERFLOW`| Prod | `20` | Maximum temporary connections above pool size under load. |

---

## 4. Object Storage Configuration

Configure which backend manages uploaded item images using `STORAGE_BACKEND`:

| Variable | Values | Description |
| :--- | :--- | :--- |
| `STORAGE_BACKEND` | `auto`, `gcs`, `oci`, `local` | `auto` detects GCS or OCI based on populated variables; falls back to `local` if neither is present. |
| `UPLOAD_FOLDER` | Local | `/app/uploads` | Filesystem directory used when `STORAGE_BACKEND=local`. |

### Google Cloud Storage (GCS)
Used when deployed on Google Cloud Compute Engine VM:
* `GCS_BUCKET`: Name of your GCS bucket (e.g. `campus-lost-found-images`).
* `GCP_PROJECT_ID`: Google Cloud Project ID.
* Authentication: Automatically uses the VM's **Compute Engine Service Account** via Application Default Credentials (ADC).

### Oracle Cloud Infrastructure (OCI) Object Storage
Used if deploying with OCI bucket:
* `OCI_NAMESPACE`: Tenancy namespace.
* `OCI_BUCKET`: Bucket name.
* `OCI_REGION`: Region identifier (e.g., `us-ashburn-1`).
* `OCI_CONFIG_FILE`: Path to OCI configuration file (default `/root/.oci/config`).
* `OCI_PROFILE`: Profile name (default `DEFAULT`).

---

## 5. GitHub Actions Secrets & Variables

### Repository Variables (Settings -> Secrets and variables -> Actions -> Variables)
* `GCP_PROJECT_ID`: Google Cloud Project ID.
* `GCP_ZONE`: Google Cloud VM zone (e.g., `us-central1-a`).
* `GCP_VM_NAME`: Google Cloud Compute Engine instance name (e.g., `lostandfound-prod`).
* `GCP_WORKLOAD_IDENTITY_PROVIDER`: Workload Identity Provider resource path (e.g., `projects/1234567890/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider`).
* `GCP_DEPLOY_SERVICE_ACCOUNT`: Service account email used by GitHub Actions (e.g., `github-deployer@my-project.iam.gserviceaccount.com`).
* `DEPLOY_DOMAIN`: Registered DNS domain name for HTTPS routing (e.g., `lostandfound.campus.edu`).

### Repository Secrets (Settings -> Secrets and variables -> Actions -> Secrets)
* `SSH_PRIVATE_KEY`: *(Optional if using Workload Identity Federation / IAP)* Private SSH key if direct SSH access is chosen.
* `SSH_KNOWN_HOSTS`: *(Optional if using direct SSH)* Host key fingerprint for the VM.
