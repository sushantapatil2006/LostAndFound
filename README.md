# Campus Lost & Found Portal

A secure, production-ready web application for campus communities to report, search, and recover lost and found belongings.

Built with a decoupled static frontend, Python Flask/Gunicorn backend, MySQL 8.4 database, and cloud object storage (Google Cloud Storage or Oracle Cloud Infrastructure Object Storage), containerized with Docker and deployed to Google Cloud Compute Engine via GitHub Actions CI/CD.

---

## 1. Technology Stack

* **Frontend**: Vanilla HTML5, CSS3, ES6+ JavaScript, served via **Nginx 1.27 Alpine** with automated security headers and reverse proxy.
* **Backend**: **Python 3.12**, **Flask 3.1**, **Flask-SQLAlchemy**, **Gunicorn 23**, **PyJWT**, non-root container security.
* **Database**: **MySQL 8.4** with InnoDB engine, utf8mb4 character set, persistent Docker volume storage.
* **Storage Abstraction**: Pluggable storage providers supporting **Google Cloud Storage (GCS)**, **OCI Object Storage**, and **Local Filesystem** storage.
* **Reverse Proxy & TLS**: **Caddy** with automatic HTTPS / Let's Encrypt certificates.
* **CI/CD**: **GitHub Actions** workflows for automated linting, pytest suites, MySQL integration tests, GHCR container publishing, and automated minimal-downtime deployment with automatic rollbacks.

---

## 2. Quick Start: Local Development (Docker Compose)

The easiest way to run the full stack locally:

```bash
# 1. Clone the repository
git clone https://github.com/sushantapatil2006/LostAndFound.git
cd LostAndFound

# 2. Start all services (Frontend, API, and MySQL)
docker compose up --build
```

Access the application in your browser:
* **Frontend Portal**: [http://localhost:8080](http://localhost:8080)
* **Backend API Health Check**: [http://localhost:8080/api/health](http://localhost:8080/api/health)
* **Database Readiness Check**: [http://localhost:8080/api/ready](http://localhost:8080/api/ready)

---

## 3. Local Development (Without Docker)

### Run the Backend
```bash
cd backend
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
export DATABASE_URL="sqlite:///lost_found.db"
export SECRET_KEY="dev-secret-key"
export STORAGE_BACKEND="local"
python app.py
```

### Run the Frontend
```bash
cd frontend
python -m http.server 8080
```
Open [http://localhost:8080](http://localhost:8080) in your browser.

---

## 4. Running Tests

The test suite runs 30+ comprehensive unit and integration tests covering authentication, JWT expiration, item retrieval, search filtering, ownership rules, file magic-byte validation, and health checks:

```bash
cd backend
pytest -v --cov=.
```

---

## 5. API Endpoints

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | No | Liveness probe returning service status. |
| `GET` | `/api/ready` | No | Readiness probe verifying database connectivity. |
| `POST` | `/api/register` | No | Register new user account. |
| `POST` | `/api/login` | No | Authenticate user and receive JWT. |
| `GET` | `/api/items` | No | List items (supports `?type=lost\|found` & `?status=open\|recovered`). |
| `POST` | `/api/items` | **Yes (Bearer)** | Create item with optional photo upload. |
| `GET` | `/api/search` | No | Search listings (`?q=keyword`). |
| `PATCH`| `/api/items/<id>/status`| **Yes (Owner/Admin)** | Update status (`open` or `recovered`). |
| `DELETE`| `/api/admin/items/<id>`| **Yes (Admin)** | Delete listing and attached photo. |
| `POST` | `/api/admin/bootstrap`| Token | Promote account using `ADMIN_BOOTSTRAP_TOKEN`. |

---

## 6. Production Deployment & Documentation

Detailed operational guides are located in the `docs/` directory:

* 📖 [**Production Deployment Guide**](docs/DEPLOYMENT.md): Step-by-step instructions for provisioning a Google Cloud Compute Engine VM, configuring firewall rules, setting up Workload Identity Federation, and running Caddy.
* 🚀 [**CI/CD Pipeline Guide**](docs/CICD.md): Architecture of the GitHub Actions pipeline, GHCR publishing, and continuous deployment workflows.
* 🔒 [**Security Architecture**](docs/SECURITY.md): Threat modeling, admin elevation defense, non-root containers, magic byte file validation, and input sanitization.
* 🔄 [**Rollback & Disaster Recovery**](docs/ROLLBACK.md): Automated and manual rollback instructions and MySQL backup restoration procedures.
* ⚙️ [**Environment Variables Reference**](docs/ENVIRONMENT.md): Complete reference for all application and infrastructure configuration parameters.
