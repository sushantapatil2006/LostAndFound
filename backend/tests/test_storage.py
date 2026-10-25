import io
import pytest
from werkzeug.datastructures import FileStorage
from storage import validate_image, LocalStorage


def test_validate_image_valid_png():
    # PNG Magic bytes: \x89PNG\r\n\x1a\n
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
    file = FileStorage(
        stream=io.BytesIO(png_bytes),
        filename="test.png",
        content_type="image/png",
    )
    ext = validate_image(file)
    assert ext == "png"


def test_validate_image_valid_jpg():
    # JPEG Magic bytes: \xff\xd8\xff
    jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50
    file = FileStorage(
        stream=io.BytesIO(jpg_bytes),
        filename="photo.jpg",
        content_type="image/jpeg",
    )
    ext = validate_image(file)
    assert ext == "jpg"


def test_validate_image_valid_webp():
    # WebP: RIFF....WEBP
    webp_bytes = b"RIFF\x14\x00\x00\x00WEBPVP8 " + b"\x00" * 20
    file = FileStorage(
        stream=io.BytesIO(webp_bytes),
        filename="image.webp",
        content_type="image/webp",
    )
    ext = validate_image(file)
    assert ext == "webp"


def test_validate_image_spoofed_content():
    # Fake PNG containing plain text
    text_bytes = b"This is plain text pretending to be an image."
    file = FileStorage(
        stream=io.BytesIO(text_bytes),
        filename="fake.png",
        content_type="image/png",
    )
    with pytest.raises(ValueError, match="does not match PNG format"):
        validate_image(file)


def test_validate_image_disallowed_extension():
    file = FileStorage(
        stream=io.BytesIO(b"executable content"),
        filename="script.exe",
        content_type="application/octet-stream",
    )
    with pytest.raises(ValueError, match="Only JPG, PNG, and WebP"):
        validate_image(file)


def test_validate_image_too_large():
    large_stream = io.BytesIO(b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024))
    file = FileStorage(
        stream=large_stream,
        filename="huge.jpg",
        content_type="image/jpeg",
    )
    with pytest.raises(ValueError, match="5 MB or smaller"):
        validate_image(file)


def test_validate_image_empty():
    file = FileStorage(
        stream=io.BytesIO(b""),
        filename="empty.jpg",
        content_type="image/jpeg",
    )
    with pytest.raises(ValueError, match="empty"):
        validate_image(file)


def test_local_storage_upload_and_delete(tmp_path):
    storage = LocalStorage({"UPLOAD_FOLDER": str(tmp_path)})
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
    file = FileStorage(
        stream=io.BytesIO(png_bytes),
        filename="test.png",
        content_type="image/png",
    )
    obj_name, url = storage.upload(file, "png")
    assert obj_name.startswith("items/")
    assert url.startswith("/api/images/")
    assert (tmp_path / obj_name).exists()

    storage.delete(obj_name)
    assert not (tmp_path / obj_name).exists()
