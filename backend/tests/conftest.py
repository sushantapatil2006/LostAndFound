import os
import sys
import shutil
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User, Item
from storage import LocalStorage


class TestConfig:
    TESTING = True
    ENV = "testing"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret-key-do-not-use-in-production"
    JWT_EXPIRY_HOURS = 1
    AUTO_CREATE_TABLES = True
    ADMIN_BOOTSTRAP_TOKEN = "test-bootstrap-secret"
    ADMIN_EMAILS = {"admin@campus.test"}
    AUTO_ADMIN_REGISTRATION = False
    STORAGE_BACKEND = "local"


@pytest.fixture
def app():
    temp_dir = tempfile.mkdtemp()
    TestConfig.UPLOAD_FOLDER = temp_dir

    app = create_app(config_object=TestConfig, validate_config=False)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_user(client):
    response = client.post(
        "/api/register",
        json={"name": "Alice Student", "email": "alice@campus.test", "password": "password123"},
    )
    data = response.get_json()
    return {"token": data["token"], "user": data["user"]}


@pytest.fixture
def admin_user(client):
    response = client.post(
        "/api/register",
        headers={"X-Admin-Bootstrap-Token": "test-bootstrap-secret"},
        json={"name": "Admin Officer", "email": "admin@campus.test", "password": "AdminPassword123!"},
    )
    data = response.get_json()
    return {"token": data["token"], "user": data["user"]}
