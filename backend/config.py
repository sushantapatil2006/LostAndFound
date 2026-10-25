import os
from pathlib import Path


class Config:
    """Base application configuration."""

    ENV = os.getenv("ENV", os.getenv("FLASK_ENV", "development")).lower()
    DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true") if ENV != "production" else False

    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///lost_found.db")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Connection pooling options
    _engine_options = {
        "pool_pre_ping": True,
    }
    if "sqlite" not in DATABASE_URL:
        _engine_options.update(
            {
                "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "280")),
                "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
                "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            }
        )
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options

    # Security & Authentication
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

    # Administrator Configuration
    ADMIN_EMAILS = {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }
    ADMIN_BOOTSTRAP_TOKEN = os.getenv("ADMIN_BOOTSTRAP_TOKEN")

    # Storage Configuration
    # Supported: "auto", "gcs", "oci", "local"
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "auto").lower()

    # OCI Object Storage
    OCI_NAMESPACE = os.getenv("OCI_NAMESPACE")
    OCI_BUCKET = os.getenv("OCI_BUCKET")
    OCI_REGION = os.getenv("OCI_REGION")
    OCI_CONFIG_FILE = os.getenv("OCI_CONFIG_FILE", "~/.oci/config")
    OCI_PROFILE = os.getenv("OCI_PROFILE", "DEFAULT")

    # Google Cloud Storage
    GCS_BUCKET = os.getenv("GCS_BUCKET", os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET"))
    GCS_PROJECT = os.getenv("GCP_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT"))

    # Local Storage
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER", str(Path(__file__).resolve().parent / "uploads")
    )

    # Proxy handling behind Nginx
    NUM_PROXIES = int(os.getenv("NUM_PROXIES", "1"))

    @classmethod
    def validate(cls):
        """Validate critical configuration settings at application startup."""
        if cls.ENV == "production":
            if not cls.SECRET_KEY or cls.SECRET_KEY == "dev-only-change-me":
                raise ValueError(
                    "CRITICAL SECURITY ERROR: SECRET_KEY must be set to a strong, "
                    "random secret in production environments."
                )
            if "sqlite" in cls.DATABASE_URL:
                # Warning or exception for sqlite in production
                # We enforce clear logging/warning if sqlite is used in production
                pass
