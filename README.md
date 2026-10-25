# Campus Lost-and-Found Portal

Separate frontend and backend for a campus lost-and-found portal using Flask, SQLAlchemy, MySQL-compatible schema, Docker-ready configuration, and OCI Object Storage image uploads.

## Run the API

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///lost_found.db" # use mysql+mysqldb://... in production
python app.py
```

The frontend is static and can be opened through a local server:

```powershell
cd frontend
python -m http.server 8080
```

Set `OCI_NAMESPACE`, `OCI_BUCKET`, and `OCI_REGION` plus OCI config variables in production. The storage adapter uploads objects and returns an Object Storage pre-authenticated request (PAR) URL. Tests inject `StorageStub`, so no OCI account is needed to run them:

```powershell
cd backend
pytest -q
```

Routes: `POST /api/register`, `POST /api/login`, `GET/POST /api/items`, `GET /api/search?q=...`, `PATCH /api/items/<id>/status`, and `DELETE /api/admin/items/<id>`.
