import mimetypes
import os
import uuid
from pathlib import Path

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def validate_image(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("An image file is required")
    extension = Path(file_storage.filename).suffix.lower().lstrip(".")
    content_type = (file_storage.content_type or "").lower()
    if extension not in ALLOWED_EXTENSIONS or content_type not in ALLOWED_MIME_TYPES:
        raise ValueError("Only JPG, PNG, and WebP images are allowed")
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_IMAGE_BYTES:
        raise ValueError("Image must be 5 MB or smaller")
    return extension


class OCIStorage:
    """OCI Object Storage adapter. Tests can replace this with the storage stub."""

    def __init__(self, config):
        self.namespace = config.get("OCI_NAMESPACE")
        self.bucket = config.get("OCI_BUCKET")
        self.region = config.get("OCI_REGION")
        self.config_file = os.path.expanduser(config.get("OCI_CONFIG_FILE", "~/.oci/config"))
        self.profile = config.get("OCI_PROFILE", "DEFAULT")
        self._client = None

    def _get_client(self):
        if self._client is None:
            import oci

            oci_config = oci.config.from_file(self.config_file, self.profile)
            self._client = oci.object_storage.ObjectStorageClient(oci_config)
        return self._client

    def upload(self, file_storage, extension):
        object_name = f"items/{uuid.uuid4().hex}.{extension}"
        self._get_client().put_object(
            self.namespace,
            self.bucket,
            object_name,
            file_storage.stream,
            content_type=file_storage.content_type,
        )
        return object_name, self.create_par(object_name)

    def create_par(self, object_name, expires_hours=24):
        import datetime
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

    def delete(self, object_name):
        self._get_client().delete_object(self.namespace, self.bucket, object_name)
