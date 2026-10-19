"""
Flask REST API for the inventory management system.

Endpoints:
    GET    /inventory          -> list all items (optional ?name= filter)
    GET    /inventory/<id>     -> fetch a single item
    POST   /inventory          -> add a new item
    PATCH  /inventory/<id>     -> update fields of an item
    DELETE /inventory/<id>     -> remove an item

Helper routes:
    GET    /inventory/low-stock?threshold= -> items that need restocking

Helper routes (OpenFoodFacts):
    GET    /external/product/<barcode> -> look up a product by barcode
    GET    /external/search?name=      -> search products by name
    POST   /inventory/import           -> fetch a product by barcode and add it
"""

from flask import Flask, jsonify, request

from data import find_item, inventory, next_id
from external_api import (
    ExternalAPIError,
    fetch_product_by_barcode,
    search_products_by_name,
)

# Fields a client is allowed to set on an item.
ALLOWED_FIELDS = {
    "barcode",
    "product_name",
    "brands",
    "ingredients_text",
    "categories",
    "price",
    "stock",
}


def validate_fields(payload, require_name=False):
    """
    Validate an incoming JSON payload.

    Returns an error message string, or None if the payload is valid.
    """
    if not isinstance(payload, dict):
        return "Request body must be a JSON object"

    unknown = set(payload) - ALLOWED_FIELDS
    if unknown:
        return f"Unknown field(s): {', '.join(sorted(unknown))}"

    if require_name and not str(payload.get("product_name", "")).strip():
        return "product_name is required"

    if "price" in payload:
        price = payload["price"]
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
            return "price must be a non-negative number"

    if "stock" in payload:
        stock = payload["stock"]
        if isinstance(stock, bool) or not isinstance(stock, int) or stock < 0:
            return "stock must be a non-negative integer"

    return None


def create_app():
    """Application factory: builds and returns the Flask app."""
    app = Flask(__name__)

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": "Method not allowed"}), 405

    # ---------- CRUD routes ----------

    @app.get("/inventory")
    def get_inventory():
        """Return all items, optionally filtered by ?name= (case-insensitive)."""
        name = request.args.get("name", "").strip().lower()
        if name:
            results = [i for i in inventory if name in i["product_name"].lower()]
            return jsonify(results), 200
        return jsonify(inventory), 200

    @app.get("/inventory/low-stock")
    def low_stock():
        """Return items whose stock is at or below ?threshold= (default 10)."""
        threshold = request.args.get("threshold", "10")
        if not threshold.isdigit():
            return jsonify({"error": "threshold must be a non-negative integer"}), 400
        results = [i for i in inventory if i["stock"] <= int(threshold)]
        return jsonify(results), 200

    @app.get("/inventory/<int:item_id>")
    def get_item(item_id):
        """Return one item by id."""
        item = find_item(item_id)
        if item is None:
            return jsonify({"error": f"Item {item_id} not found"}), 404
        return jsonify(item), 200

    @app.post("/inventory")
    def add_item():
        """Create a new item from the JSON body."""
        payload = request.get_json(silent=True)
        error = validate_fields(payload, require_name=True)
        if error:
            return jsonify({"error": error}), 400

        item = {
            "id": next_id(),
            "barcode": payload.get("barcode", ""),
            "product_name": payload["product_name"].strip(),
            "brands": payload.get("brands", ""),
            "ingredients_text": payload.get("ingredients_text", ""),
            "categories": payload.get("categories", ""),
            "price": payload.get("price", 0.0),
            "stock": payload.get("stock", 0),
        }
        inventory.append(item)
        return jsonify(item), 201

    @app.patch("/inventory/<int:item_id>")
    def update_item(item_id):
        """Partially update an item (e.g. price or stock)."""
        item = find_item(item_id)
        if item is None:
            return jsonify({"error": f"Item {item_id} not found"}), 404

        payload = request.get_json(silent=True)
        error = validate_fields(payload)
        if error:
            return jsonify({"error": error}), 400
        if not payload:
            return jsonify({"error": "No fields to update"}), 400
        if "product_name" in payload and not str(payload["product_name"]).strip():
            return jsonify({"error": "product_name cannot be empty"}), 400

        item.update(payload)
        return jsonify(item), 200

    @app.delete("/inventory/<int:item_id>")
    def delete_item(item_id):
        """Remove an item from the inventory."""
        item = find_item(item_id)
        if item is None:
            return jsonify({"error": f"Item {item_id} not found"}), 404
        inventory.remove(item)
        return jsonify({"message": f"Item {item_id} deleted", "item": item}), 200

    # ---------- External API helper routes ----------

    @app.get("/external/product/<barcode>")
    def external_product(barcode):
        """Look up a product on OpenFoodFacts by barcode (does not save it)."""
        try:
            product = fetch_product_by_barcode(barcode)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except ExternalAPIError as exc:
            return jsonify({"error": str(exc)}), 502
        if product is None:
            return jsonify({"error": f"No product found for barcode {barcode}"}), 404
        return jsonify(product), 200

    @app.get("/external/search")
    def external_search():
        """Search OpenFoodFacts by product name (does not save results)."""
        name = request.args.get("name", "")
        try:
            products = search_products_by_name(name)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except ExternalAPIError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify(products), 200

    @app.post("/inventory/import")
    def import_item():
        """
        Fetch a product from OpenFoodFacts by barcode and add it to inventory.

        Body: {"barcode": "...", "price": 2.5, "stock": 10}
        """
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not payload.get("barcode"):
            return jsonify({"error": "barcode is required"}), 400

        barcode = str(payload["barcode"]).strip()
        store_fields = {k: payload[k] for k in ("price", "stock") if k in payload}
        error = validate_fields(store_fields)
        if error:
            return jsonify({"error": error}), 400

        if any(item.get("barcode") == barcode for item in inventory):
            return jsonify({"error": f"Barcode {barcode} is already in inventory"}), 409

        try:
            product = fetch_product_by_barcode(barcode)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except ExternalAPIError as exc:
            return jsonify({"error": str(exc)}), 502
        if product is None:
            return jsonify({"error": f"No product found for barcode {barcode}"}), 404

        item = {
            "id": next_id(),
            **product,
            "product_name": product["product_name"] or f"Unnamed product {barcode}",
            "price": store_fields.get("price", 0.0),
            "stock": store_fields.get("stock", 0),
        }
        inventory.append(item)
        return jsonify(item), 201

    return app


if __name__ == "__main__":
    # debug=True enables Flask Debug Mode (auto-reload + detailed errors).
    create_app().run(debug=True, port=5000)