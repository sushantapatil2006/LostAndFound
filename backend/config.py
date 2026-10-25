import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///lost_found.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    OCI_NAMESPACE = os.getenv("OCI_NAMESPACE")
    OCI_BUCKET = os.getenv("OCI_BUCKET")
    OCI_REGION = os.getenv("OCI_REGION")
    OCI_CONFIG_FILE = os.getenv("OCI_CONFIG_FILE", "~/.oci/config")
    OCI_PROFILE = os.getenv("OCI_PROFILE", "DEFAULT")
    ADMIN_EMAILS = {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }
