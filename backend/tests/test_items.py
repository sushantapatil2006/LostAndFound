import io


def test_create_item_unauthorized(client):
    response = client.post(
        "/api/items",
        data={"title": "Lost Watch", "description": "Silver", "item_type": "lost", "location": "Gym"},
    )
    assert response.status_code == 401


def test_create_item_success(client, registered_user):
    token = registered_user["token"]
    response = client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Lost Watch", "description": "Silver wrist watch", "item_type": "lost", "location": "Gym"},
    )
    assert response.status_code == 201
    item = response.get_json()["item"]
    assert item["title"] == "Lost Watch"
    assert item["status"] == "open"
    assert item["item_type"] == "lost"


def test_create_item_missing_fields(client, registered_user):
    token = registered_user["token"]
    response = client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Lost Watch"},
    )
    assert response.status_code == 400


def test_create_item_invalid_type(client, registered_user):
    token = registered_user["token"]
    response = client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Item", "description": "Desc", "item_type": "stolen", "location": "Gym"},
    )
    assert response.status_code == 400


def test_get_items_and_filtering(client, registered_user):
    token = registered_user["token"]
    client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Blue Backpack", "description": "Desc", "item_type": "lost", "location": "Library"},
    )
    client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Set of Keys", "description": "Brass keys", "item_type": "found", "location": "Cafeteria"},
    )

    all_res = client.get("/api/items")
    assert all_res.status_code == 200
    assert len(all_res.get_json()["items"]) == 2

    lost_res = client.get("/api/items?type=lost")
    assert len(lost_res.get_json()["items"]) == 1
    assert lost_res.get_json()["items"][0]["title"] == "Blue Backpack"

    found_res = client.get("/api/items?type=found")
    assert len(found_res.get_json()["items"]) == 1
    assert found_res.get_json()["items"][0]["title"] == "Set of Keys"


def test_search_items(client, registered_user):
    token = registered_user["token"]
    client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Graphing Calculator", "description": "TI-84 Plus", "item_type": "found", "location": "Hall A"},
    )

    search_res = client.get("/api/search?q=calculator")
    assert search_res.status_code == 200
    items = search_res.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Graphing Calculator"

    empty_res = client.get("/api/search?q=umbrella")
    assert len(empty_res.get_json()["items"]) == 0


def test_update_status_ownership(client, registered_user, admin_user):
    # User 1 creates an item
    user1_token = registered_user["token"]
    create_res = client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {user1_token}"},
        data={"title": "Phone", "description": "Black phone", "item_type": "lost", "location": "Quad"},
    )
    item_id = create_res.get_json()["item"]["id"]

    # User 2 registers
    user2_res = client.post(
        "/api/register",
        json={"name": "User 2", "email": "user2@campus.test", "password": "password123"},
    )
    user2_token = user2_res.get_json()["token"]

    # User 2 tries to update status -> 403 Forbidden
    forbidden_res = client.patch(
        f"/api/items/{item_id}/status",
        headers={"Authorization": f"Bearer {user2_token}"},
        json={"status": "recovered"},
    )
    assert forbidden_res.status_code == 403

    # Owner updates status -> 200 OK
    owner_res = client.patch(
        f"/api/items/{item_id}/status",
        headers={"Authorization": f"Bearer {user1_token}"},
        json={"status": "recovered"},
    )
    assert owner_res.status_code == 200
    assert owner_res.get_json()["item"]["status"] == "recovered"

    # Admin can also update status -> 200 OK
    admin_token = admin_user["token"]
    admin_res = client.patch(
        f"/api/items/{item_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "open"},
    )
    assert admin_res.status_code == 200
    assert admin_res.get_json()["item"]["status"] == "open"


def test_admin_delete_authorization(client, registered_user, admin_user):
    # Non-admin creates item
    user_token = registered_user["token"]
    res = client.post(
        "/api/items",
        headers={"Authorization": f"Bearer {user_token}"},
        data={"title": "Scarf", "description": "Red wool", "item_type": "found", "location": "Bench"},
    )
    item_id = res.get_json()["item"]["id"]

    # Non-admin tries to delete -> 403 Forbidden
    del_res = client.delete(
        f"/api/admin/items/{item_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert del_res.status_code == 403

    # Admin deletes -> 200 OK
    admin_token = admin_user["token"]
    del_admin_res = client.delete(
        f"/api/admin/items/{item_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_admin_res.status_code == 200
    assert del_admin_res.get_json()["message"] == "Item deleted"

    # Confirm item is gone
    get_res = client.get("/api/items")
    assert len(get_res.get_json()["items"]) == 0
