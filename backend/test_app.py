from app import app


def test_backend_app_routes_load():
    client = app.test_client()
    response = client.get("/api/items")

    assert response.status_code == 200
    assert "items" in response.get_json()
