"""Tests for the CRUD endpoints in app.py."""

from data import inventory


# ---------- GET ----------

def test_get_all_items(client):
    response = client.get("/inventory")
    assert response.status_code == 200
    assert len(response.get_json()) == 3


def test_get_items_filtered_by_name(client):
    response = client.get("/inventory?name=nutella")
    data = response.get_json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["brands"] == "Ferrero"


def test_get_single_item(client):
    response = client.get("/inventory/1")
    assert response.status_code == 200
    assert response.get_json()["product_name"] == "Organic Almond Milk"


def test_get_missing_item_returns_404(client):
    response = client.get("/inventory/999")
    assert response.status_code == 404
    assert "error" in response.get_json()


# ---------- POST ----------

def test_add_item(client):
    new_item = {"product_name": "Brown Bread", "brands": "Festive", "price": 0.99, "stock": 10}
    response = client.post("/inventory", json=new_item)
    data = response.get_json()
    assert response.status_code == 201
    assert data["id"] == 4
    assert data["product_name"] == "Brown Bread"
    assert len(inventory) == 4


def test_add_item_requires_name(client):
    response = client.post("/inventory", json={"price": 1.0})
    assert response.status_code == 400
    assert len(inventory) == 3


def test_add_item_rejects_negative_price(client):
    response = client.post("/inventory", json={"product_name": "X", "price": -5})
    assert response.status_code == 400


def test_add_item_rejects_non_integer_stock(client):
    response = client.post("/inventory", json={"product_name": "X", "stock": "lots"})
    assert response.status_code == 400


def test_add_item_rejects_unknown_fields(client):
    response = client.post("/inventory", json={"product_name": "X", "colour": "red"})
    assert response.status_code == 400


def test_add_item_rejects_non_json_body(client):
    response = client.post("/inventory", data="not json")
    assert response.status_code == 400


# ---------- PATCH ----------

def test_update_price_and_stock(client):
    response = client.patch("/inventory/1", json={"price": 4.50, "stock": 30})
    data = response.get_json()
    assert response.status_code == 200
    assert data["price"] == 4.50
    assert data["stock"] == 30
    # The change must be persisted in the array, not just echoed back.
    assert client.get("/inventory/1").get_json()["stock"] == 30


def test_update_missing_item_returns_404(client):
    response = client.patch("/inventory/999", json={"price": 1.0})
    assert response.status_code == 404


def test_update_with_invalid_stock(client):
    response = client.patch("/inventory/1", json={"stock": -1})
    assert response.status_code == 400


def test_update_with_empty_body(client):
    response = client.patch("/inventory/1", json={})
    assert response.status_code == 400


def test_update_cannot_change_id(client):
    response = client.patch("/inventory/1", json={"id": 50})
    assert response.status_code == 400


# ---------- DELETE ----------

def test_delete_item(client):
    response = client.delete("/inventory/2")
    assert response.status_code == 200
    assert len(inventory) == 2
    assert client.get("/inventory/2").status_code == 404


def test_delete_missing_item_returns_404(client):
    response = client.delete("/inventory/999")
    assert response.status_code == 404


def test_new_id_does_not_reuse_existing(client):
    client.delete("/inventory/1")
    response = client.post("/inventory", json={"product_name": "Eggs"})
    assert response.get_json()["id"] == 4



# ---------- Low stock report ----------

def test_low_stock_default_threshold(client):
    client.patch("/inventory/1", json={"stock": 5})
    response = client.get("/inventory/low-stock")
    data = response.get_json()
    assert response.status_code == 200
    assert [i["id"] for i in data] == [1]


def test_low_stock_custom_threshold(client):
    response = client.get("/inventory/low-stock?threshold=40")
    assert [i["id"] for i in response.get_json()] == [1, 2]


def test_low_stock_none_below_threshold(client):
    assert client.get("/inventory/low-stock?threshold=0").get_json() == []


def test_low_stock_invalid_threshold(client):
    assert client.get("/inventory/low-stock?threshold=abc").status_code == 400