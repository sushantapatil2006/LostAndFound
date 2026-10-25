import datetime
import logging
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_image(file_storage):
    """
    Validate that an uploaded file is a valid image within size and format constraints.
    Performs content (magic-byte) verification in addition to extension and MIME-type checks.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("An image file is required")

    extension = Path(file_storage.filename).suffix.lower().lstrip(".")
    content_type = (file_storage.content_type or "").lower()

    if extension not in ALLOWED_EXTENSIONS or content_type not in ALLOWED_MIME_TYPES:
        raise ValueError("Only JPG, PNG, and WebP images are allowed")

    # Check file size
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if size == 0:
        raise ValueError("Uploaded image file is empty")
    if size > MAX_IMAGE_BYTES:
        raise ValueError("Image must be 5 MB or smaller")

    # Magic byte inspection for genuine image formats
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)

    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"

    if extension in {"jpg", "jpeg"} and not is_jpeg:
        raise ValueError("File content does not match JPEG format")
    elif extension == "png" and not is_png:
        raise ValueError("File content does not match PNG format")
    elif extension == "webp" and not is_webp:
        raise ValueError("File content does not match WebP format")

    return extension


class BaseStorage(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    def upload(self, file_storage, extension: str) -> tuple[str, str]:
        """Upload file and return (object_name, public_or_par_url)."""
        pass

    @abstractmethod
    def delete(self, object_name: str) -> None:
        """Delete object from storage."""
        pass


class LocalStorage(BaseStorage):
    """Local filesystem storage provider for development, tests, or fallback."""

    def __init__(self, config):
        self.upload_dir = Path(config.get("UPLOAD_FOLDER", "uploads"))
        self.items_dir = self.upload_dir / "items"
        self.items_dir.mkdir(parents=True, exist_ok=True)

    def upload(self, file_storage, extension: str) -> tuple[str, str]:
        filename = f"{uuid.uuid4().hex}.{extension}"
        target_path = self.items_dir / filename
        file_storage.stream.seek(0)
        with open(target_path, "wb") as f:
            f.write(file_storage.stream.read())
        object_name = f"items/{filename}"
        url = f"/api/images/{filename}"
        return object_name, url

    def delete(self, object_name: str) -> None:
        filename = Path(object_name).name
        target_path = self.items_dir / filename
        if target_path.exists():
            target_path.unlink()


class OCIStorage(BaseStorage):
    """Oracle Cloud Infrastructure Object Storage provider."""

    def __init__(self, config):
        self.namespace = config.get("OCI_NAMESPACE")
        self.bucket = config.get("OCI_BUCKET")
        self.region = config.get("OCI_REGION")
        self.config_file = os.path.expanduser(config.get("OCI_CONFIG_FILE", "~/.oci/config"))
        self.profile = config.get("OCI_PROFILE", "DEFAULT")
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.namespace or not self.bucket:
                raise ValueError("OCI_NAMESPACE and OCI_BUCKET must be configured for OCI storage.")
            import oci

            oci_config = oci.config.from_file(self.config_file, self.profile)
            self._client = oci.object_storage.ObjectStorageClient(oci_config)
        return self._client

    def upload(self, file_storage, extension: str) -> tuple[str, str]:
        object_name = f"items/{uuid.uuid4().hex}.{extension}"
        file_storage.stream.seek(0)
        self._get_client().put_object(
            self.namespace,
            self.bucket,
            object_name,
            file_storage.stream,
            content_type=file_storage.content_type,
        )
        return object_name, self.create_par(object_name)

    def create_par(self, object_name: str, expires_hours: int = 24) -> str:
        import oci

        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            hours=expires_hours
        )
        details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name=f"read-{object_name}",
            object_name=object_name,
            access_type="ObjectRead",
            time_expires=expires,
        )
        response = self._get_client().create_preauthenticated_request(
            self.namespace, self.bucket, details
        )
        return f"https://objectstorage.{self.region}.oraclecloud.com{response.data.access_uri}"

    def delete(self, object_name: str) -> None:
        try:
            self._get_client().delete_object(self.namespace, self.bucket, object_name)
        except Exception as exc:
            logger.warning(f"Failed to delete OCI object {object_name}: {exc}")


class GCSStorage(BaseStorage):
    """Google Cloud Storage provider utilizing Application Default Credentials."""

    def __init__(self, config):
        self.bucket_name = config.get("GCS_BUCKET")
        self.project_id = config.get("GCS_PROJECT")
        self._client = None
        self._bucket = None

    def _get_bucket(self):
        if self._bucket is None:
            if not self.bucket_name:
                raise ValueError("GCS_BUCKET environment variable must be configured for GCS storage.")
            from google.cloud import storage as gcs

            self._client = gcs.Client(project=self.project_id)
            self._bucket = self._client.bucket(self.bucket_name)
        return self._bucket

    def upload(self, file_storage, extension: str) -> tuple[str, str]:
        object_name = f"items/{uuid.uuid4().hex}.{extension}"
        bucket = self._get_bucket()
        blob = bucket.blob(object_name)

        file_storage.stream.seek(0)
        blob.upload_from_file(
            file_storage.stream,
            content_type=file_storage.content_type,
        )

        url = self._generate_url(blob, object_name)
        return object_name, url

    def _generate_url(self, blob, object_name: str) -> str:
        # Attempt signed URL generation if credentials permit
        try:
            return blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(hours=24),
                method="GET",
            )
        except Exception as exc:
            # On Google Compute Engine instances, ADC (metadata credentials) lack private keys
            # to sign blobs locally without IAM credentials signBlob permissions.
            # Fall back to standard public or origin HTTPS URL.
            logger.info(
                f"Signed URL generation not available with current credentials ({exc}). "
                "Using direct Google Cloud Storage endpoint URL."
            )
            return f"https://storage.googleapis.com/{self.bucket_name}/{object_name}"

    def delete(self, object_name: str) -> None:
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(object_name)
            if blob.exists():
                blob.delete()
        except Exception as exc:
            logger.warning(f"Failed to delete GCS blob {object_name}: {exc}")


def get_storage_provider(config) -> BaseStorage:
    """Factory to instantiate the appropriate storage backend."""
    backend = config.get("STORAGE_BACKEND", "auto").lower()

    if backend == "local":
        return LocalStorage(config)
    elif backend == "oci":
        return OCIStorage(config)
    elif backend == "gcs":
        return GCSStorage(config)
    elif backend == "auto":
        # Auto-detect configured cloud provider
        if config.get("GCS_BUCKET"):
            return GCSStorage(config)
        elif config.get("OCI_BUCKET") and config.get("OCI_NAMESPACE"):
            return OCIStorage(config)
        else:
            logger.info("No cloud storage configured; using LocalStorage backend.")
            return LocalStorage(config)
    else:
        raise ValueError(f"Unsupported STORAGE_BACKEND: '{backend}'. Expected: auto, gcs, oci, local.")
