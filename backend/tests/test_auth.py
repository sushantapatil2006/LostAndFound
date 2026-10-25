import time
import jwt
from datetime import datetime, timedelta, timezone


def test_register_success(client):
    response = client.post(
        "/api/register",
        json={"name": "Bob Test", "email": "bob@campus.test", "password": "securepassword123"},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert "token" in data
    assert data["user"]["email"] == "bob@campus.test"
    assert data["user"]["name"] == "Bob Test"
    assert data["user"]["is_admin"] is False


def test_register_invalid_email(client):
    response = client.post(
        "/api/register",
        json={"name": "Invalid", "email": "not-an-email", "password": "securepassword123"},
    )
    assert response.status_code == 400
    assert "Invalid email format" in response.get_json()["error"]


def test_register_short_password(client):
    response = client.post(
        "/api/register",
        json={"name": "Short", "email": "short@campus.test", "password": "123"},
    )
    assert response.status_code == 400
    assert "at least 8 characters" in response.get_json()["error"]


def test_register_duplicate_email(client, registered_user):
    response = client.post(
        "/api/register",
        json={"name": "Alice Duplicate", "email": "alice@campus.test", "password": "password123"},
    )
    assert response.status_code == 409
    assert "already registered" in response.get_json()["error"]


def test_admin_bootstrap_protection(client):
    # Ordinary registration with admin email must NOT grant admin rights automatically
    response = client.post(
        "/api/register",
        json={"name": "Attacker", "email": "admin@campus.test", "password": "password1234"},
    )
    assert response.status_code == 201
    assert response.get_json()["user"]["is_admin"] is False


def test_admin_bootstrap_success(client):
    # Registration with valid bootstrap token grants admin rights
    response = client.post(
        "/api/register",
        headers={"X-Admin-Bootstrap-Token": "test-bootstrap-secret"},
        json={"name": "Real Admin", "email": "superadmin@campus.test", "password": "password1234"},
    )
    assert response.status_code == 201
    assert response.get_json()["user"]["is_admin"] is True


def test_login_success(client, registered_user):
    response = client.post(
        "/api/login",
        json={"email": "alice@campus.test", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "token" in data
    assert data["user"]["email"] == "alice@campus.test"


def test_login_wrong_password(client, registered_user):
    response = client.post(
        "/api/login",
        json={"email": "alice@campus.test", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.get_json()["error"]


def test_login_nonexistent_user(client):
    response = client.post(
        "/api/login",
        json={"email": "nobody@campus.test", "password": "password123"},
    )
    assert response.status_code == 401


def test_expired_token(client, app):
    # Generate expired token
    with app.app_context():
        expired_token = jwt.encode(
            {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
    response = client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {expired_token}"},
        data={"title": "Item", "description": "Desc", "item_type": "lost", "location": "Lib"},
    )
    assert response.status_code == 401
    assert "expired" in response.get_json()["error"].lower()


def test_invalid_signature_token(client):
    fake_token = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "wrong-secret-key",
        algorithm="HS256",
    )
    response = client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {fake_token}"},
        data={"title": "Item", "description": "Desc", "item_type": "lost", "location": "Lib"},
    )
    assert response.status_code == 401
    assert "Invalid or expired token" in response.get_json()["error"]
