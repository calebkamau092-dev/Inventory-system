"""
Flask REST API for the inventory management system.

Endpoints:
    GET    /inventory          -> list all items (optional ?name= filter)
    GET    /inventory/<id>     -> fetch a single item
    POST   /inventory          -> add a new item
    PATCH  /inventory/<id>     -> update fields of an item
    DELETE /inventory/<id>     -> remove an item
"""

from flask import Flask, jsonify, request

from data import find_item, inventory, next_id

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

    return app


if __name__ == "__main__":
    # debug=True enables Flask Debug Mode (auto-reload + detailed errors).
    create_app().run(debug=True, port=5000)