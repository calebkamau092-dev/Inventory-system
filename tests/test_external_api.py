"""
Tests for the OpenFoodFacts integration.

All network calls are mocked with unittest.mock, so these tests never hit
the real API and always run fast and reliably.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from data import inventory
from external_api import (
    ExternalAPIError,
    fetch_product_by_barcode,
    search_products_by_name,
)

NUTELLA_RESPONSE = {
    "status": 1,
    "code": "3017620422003",
    "product": {
        "code": "3017620422003",
        "product_name": "Nutella",
        "brands": "Ferrero",
        "ingredients_text": "Sugar, palm oil, hazelnuts",
        "categories": "Spreads",
    },
}

SEARCH_RESPONSE = {
    "count": 2,
    "products": [
        {"code": "111", "product_name": "Oat Milk", "brands": "Oatly"},
        {"code": "222", "product_name": "", "brands": "Unknown"},  # skipped: no name
    ],
}


def mock_response(status_code=200, json_data=None):
    """Build a fake requests.Response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    return response


# ---------- fetch_product_by_barcode ----------

@patch("external_api.requests.get")
def test_fetch_by_barcode_success(mock_get):
    mock_get.return_value = mock_response(200, NUTELLA_RESPONSE)
    product = fetch_product_by_barcode("3017620422003")
    assert product["product_name"] == "Nutella"
    assert product["brands"] == "Ferrero"
    assert product["barcode"] == "3017620422003"
    assert "3017620422003" in mock_get.call_args[0][0]


@patch("external_api.requests.get")
def test_fetch_by_barcode_not_found_404(mock_get):
    mock_get.return_value = mock_response(404, {"status": 0})
    assert fetch_product_by_barcode("0000000000000") is None


@patch("external_api.requests.get")
def test_fetch_by_barcode_status_zero(mock_get):
    mock_get.return_value = mock_response(200, {"status": 0})
    assert fetch_product_by_barcode("0000000000000") is None


@patch("external_api.requests.get")
def test_fetch_by_barcode_network_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("no internet")
    with pytest.raises(ExternalAPIError):
        fetch_product_by_barcode("3017620422003")


@patch("external_api.requests.get")
def test_fetch_by_barcode_server_error(mock_get):
    mock_get.return_value = mock_response(500)
    with pytest.raises(ExternalAPIError):
        fetch_product_by_barcode("3017620422003")


@patch("external_api.requests.get")
def test_fetch_by_barcode_invalid_json(mock_get):
    response = mock_response(200)
    response.json.side_effect = ValueError("bad json")
    mock_get.return_value = response
    with pytest.raises(ExternalAPIError):
        fetch_product_by_barcode("3017620422003")


def test_fetch_by_barcode_rejects_non_digits():
    with pytest.raises(ValueError):
        fetch_product_by_barcode("abc123")


# ---------- search_products_by_name ----------

@patch("external_api.requests.get")
def test_search_by_name_success(mock_get):
    mock_get.return_value = mock_response(200, SEARCH_RESPONSE)
    results = search_products_by_name("milk")
    assert len(results) == 1
    assert results[0]["product_name"] == "Oat Milk"
    assert mock_get.call_args[1]["params"]["search_terms"] == "milk"


@patch("external_api.requests.get")
def test_search_by_name_no_results(mock_get):
    mock_get.return_value = mock_response(200, {"products": []})
    assert search_products_by_name("zzzz") == []


@patch("external_api.requests.get")
def test_search_by_name_timeout(mock_get):
    mock_get.side_effect = requests.Timeout()
    with pytest.raises(ExternalAPIError):
        search_products_by_name("milk")


def test_search_by_name_rejects_empty():
    with pytest.raises(ValueError):
        search_products_by_name("   ")


# ---------- Flask helper routes ----------

@patch("app.fetch_product_by_barcode")
def test_external_product_route(mock_fetch, client):
    mock_fetch.return_value = {"barcode": "123", "product_name": "Tea"}
    response = client.get("/external/product/123")
    assert response.status_code == 200
    assert response.get_json()["product_name"] == "Tea"


@patch("app.fetch_product_by_barcode", return_value=None)
def test_external_product_route_not_found(mock_fetch, client):
    assert client.get("/external/product/123").status_code == 404


@patch("app.fetch_product_by_barcode", side_effect=ExternalAPIError("down"))
def test_external_product_route_api_failure(mock_fetch, client):
    assert client.get("/external/product/123").status_code == 502


@patch("app.search_products_by_name")
def test_external_search_route(mock_search, client):
    mock_search.return_value = [{"product_name": "Oat Milk"}]
    response = client.get("/external/search?name=milk")
    assert response.status_code == 200
    assert response.get_json()[0]["product_name"] == "Oat Milk"


def test_external_search_route_requires_name(client):
    assert client.get("/external/search").status_code == 400


@patch("app.fetch_product_by_barcode")
def test_import_adds_product_to_inventory(mock_fetch, client):
    mock_fetch.return_value = {
        "barcode": "111",
        "product_name": "Oat Milk",
        "brands": "Oatly",
        "ingredients_text": "Water, oats",
        "categories": "Plant-based milks",
    }
    response = client.post("/inventory/import", json={"barcode": "111", "price": 2.5, "stock": 12})
    data = response.get_json()
    assert response.status_code == 201
    assert data["id"] == 4
    assert data["brands"] == "Oatly"
    assert data["price"] == 2.5
    assert data["stock"] == 12
    assert len(inventory) == 4


@patch("app.fetch_product_by_barcode")
def test_import_rejects_duplicate_barcode(mock_fetch, client):
    response = client.post("/inventory/import", json={"barcode": "3017620422003"})
    assert response.status_code == 409
    mock_fetch.assert_not_called()


@patch("app.fetch_product_by_barcode", return_value=None)
def test_import_unknown_barcode(mock_fetch, client):
    response = client.post("/inventory/import", json={"barcode": "999"})
    assert response.status_code == 404
    assert len(inventory) == 3


def test_import_requires_barcode(client):
    assert client.post("/inventory/import", json={}).status_code == 400


def test_import_rejects_bad_price(client):
    response = client.post("/inventory/import", json={"barcode": "111", "price": "free"})
    assert response.status_code == 400