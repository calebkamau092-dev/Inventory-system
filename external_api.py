"""
OpenFoodFacts API integration.

Docs: https://openfoodfacts.github.io/openfoodfacts-server/api/
"""

import requests

BASE_URL = "https://world.openfoodfacts.org"
# OpenFoodFacts asks clients to identify themselves with a User-Agent.
HEADERS = {"User-Agent": "InventoryManagementSystem/1.0 (student project)"}
TIMEOUT = 10  # seconds
FIELDS = "code,product_name,brands,ingredients_text,categories"


class ExternalAPIError(Exception):
    """Raised when OpenFoodFacts cannot be reached or returns bad data."""


def _simplify(product):
    """Keep only the fields our inventory stores."""
    return {
        "barcode": product.get("code", ""),
        "product_name": product.get("product_name", "") or "",
        "brands": product.get("brands", "") or "",
        "ingredients_text": product.get("ingredients_text", "") or "",
        "categories": product.get("categories", "") or "",
    }


def fetch_product_by_barcode(barcode):
    """
    Look up a single product by barcode.

    Returns a simplified product dict, or None if the product doesn't exist.
    Raises ExternalAPIError on network or server failures.
    """
    barcode = str(barcode).strip()
    if not barcode.isdigit():
        raise ValueError("Barcode must contain digits only")

    url = f"{BASE_URL}/api/v2/product/{barcode}.json"
    try:
        response = requests.get(url, params={"fields": FIELDS}, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ExternalAPIError(f"Could not reach OpenFoodFacts: {exc}") from exc

    # OpenFoodFacts answers 404 (with status 0) for unknown barcodes.
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise ExternalAPIError(f"OpenFoodFacts returned HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise ExternalAPIError("OpenFoodFacts returned invalid JSON") from exc

    if data.get("status") != 1 or "product" not in data:
        return None

    product = data["product"]
    product.setdefault("code", barcode)
    return _simplify(product)


def search_products_by_name(name, limit=5):
    """
    Search products by name.

    Returns a list of simplified product dicts (possibly empty).
    Raises ExternalAPIError on network or server failures.
    """
    name = str(name).strip()
    if not name:
        raise ValueError("Search term cannot be empty")

    url = f"{BASE_URL}/cgi/search.pl"
    params = {
        "search_terms": name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": limit,
        "fields": FIELDS,
    }
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ExternalAPIError(f"Could not reach OpenFoodFacts: {exc}") from exc

    if response.status_code != 200:
        raise ExternalAPIError(f"OpenFoodFacts returned HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise ExternalAPIError("OpenFoodFacts returned invalid JSON") from exc

    products = data.get("products", [])[:limit]
    # Skip entries without a name; they aren't useful for inventory.
    return [_simplify(p) for p in products if p.get("product_name")]