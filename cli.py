"""
Command-line interface for the inventory API.

The Flask server (app.py) must be running. Usage:

    python cli.py                  # interactive menu
    python cli.py list             # one-off commands
    python cli.py view 1
    python cli.py add "Brown Bread" --brand Festive --price 0.99 --stock 10
    python cli.py update 1 --price 4.25 --stock 30
    python cli.py delete 1
    python cli.py find --barcode 3017620422003
    python cli.py find --name "almond milk"
    python cli.py import 3017620422003 --price 5.49 --stock 20
"""

import argparse
import os
import sys

import requests

API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:5000")
TIMEOUT = 15  # seconds


class CLIError(Exception):
    """An error that should be shown to the user (not a crash)."""


# ---------- HTTP helper ----------

def api_request(method, path, **kwargs):
    """
    Send a request to the inventory API and return the decoded JSON.

    Raises CLIError with a friendly message on connection or API errors.
    """
    try:
        response = requests.request(method, f"{API_URL}{path}", timeout=TIMEOUT, **kwargs)
    except requests.ConnectionError:
        raise CLIError(f"Cannot connect to the API at {API_URL}. Is the server running (python app.py)?")
    except requests.Timeout:
        raise CLIError("The API took too long to respond.")

    try:
        data = response.json()
    except ValueError:
        raise CLIError(f"Unexpected response from API (HTTP {response.status_code}).")

    if response.status_code >= 400:
        raise CLIError(data.get("error", f"Request failed (HTTP {response.status_code})."))
    return data


# ---------- Output formatting ----------

def format_item(item):
    """Return a multi-line, human-readable description of an item."""
    lines = [
        f"[{item['id']}] {item['product_name']}",
        f"    Brand:       {item.get('brands') or '-'}",
        f"    Barcode:     {item.get('barcode') or '-'}",
        f"    Category:    {item.get('categories') or '-'}",
        f"    Price:       ${float(item.get('price', 0)):.2f}",
        f"    Stock:       {item.get('stock', 0)}",
    ]
    if item.get("ingredients_text"):
        lines.append(f"    Ingredients: {item['ingredients_text']}")
    return "\n".join(lines)


def format_external(product):
    """Return a short description of an OpenFoodFacts product."""
    return (
        f"{product.get('product_name') or '(no name)'} - {product.get('brands') or 'unknown brand'}"
        f" (barcode: {product.get('barcode') or '-'})"
    )


# ---------- Commands (each returns the text to print) ----------

def list_items(name=None):
    params = {"name": name} if name else None
    items = api_request("GET", "/inventory", params=params)
    if not items:
        return "No items found."
    return "\n".join(f"[{i['id']}] {i['product_name']} | ${float(i['price']):.2f} | stock: {i['stock']}" for i in items)


def view_item(item_id):
    return format_item(api_request("GET", f"/inventory/{item_id}"))


def add_item(name, brand="", barcode="", price=0.0, stock=0):
    payload = {"product_name": name, "brands": brand, "barcode": barcode, "price": price, "stock": stock}
    item = api_request("POST", "/inventory", json=payload)
    return "Item added:\n" + format_item(item)


def update_item(item_id, price=None, stock=None, name=None):
    payload = {}
    if price is not None:
        payload["price"] = price
    if stock is not None:
        payload["stock"] = stock
    if name is not None:
        payload["product_name"] = name
    if not payload:
        raise CLIError("Nothing to update. Provide a price, stock or name.")
    item = api_request("PATCH", f"/inventory/{item_id}", json=payload)
    return "Item updated:\n" + format_item(item)


def delete_item(item_id):
    return api_request("DELETE", f"/inventory/{item_id}")["message"]


def find_external(barcode=None, name=None):
    if barcode:
        product = api_request("GET", f"/external/product/{barcode}")
        return "Found on OpenFoodFacts:\n  " + format_external(product)
    if name:
        products = api_request("GET", "/external/search", params={"name": name})
        if not products:
            return f"No products found for '{name}'."
        return "OpenFoodFacts results:\n" + "\n".join(f"  {n}. {format_external(p)}" for n, p in enumerate(products, 1))
    raise CLIError("Provide a barcode or a name to search for.")


def import_item(barcode, price=0.0, stock=0):
    item = api_request("POST", "/inventory/import", json={"barcode": barcode, "price": price, "stock": stock})
    return "Imported from OpenFoodFacts:\n" + format_item(item)


# ---------- Input validation helpers ----------

def parse_price(value):
    try:
        price = float(value)
    except (TypeError, ValueError):
        raise CLIError(f"Invalid price: '{value}'. Enter a number like 2.99.")
    if price < 0:
        raise CLIError("Price cannot be negative.")
    return round(price, 2)


def parse_stock(value):
    try:
        stock = int(value)
    except (TypeError, ValueError):
        raise CLIError(f"Invalid stock: '{value}'. Enter a whole number.")
    if stock < 0:
        raise CLIError("Stock cannot be negative.")
    return stock


def parse_id(value):
    try:
        item_id = int(value)
    except (TypeError, ValueError):
        raise CLIError(f"Invalid id: '{value}'. Enter a whole number.")
    if item_id < 1:
        raise CLIError("Id must be a positive number.")
    return item_id


# ---------- Interactive menu ----------

MENU = """
===== Inventory Management =====
1. List all items
2. View item details
3. Add new item
4. Update item price / stock
5. Delete item
6. Find product on OpenFoodFacts
7. Import product from OpenFoodFacts
0. Exit
"""


def run_menu_choice(choice, ask=input):
    """Run one menu option. `ask` is injectable so tests can fake user input."""
    if choice == "1":
        return list_items()
    if choice == "2":
        return view_item(parse_id(ask("Item id: ")))
    if choice == "3":
        name = ask("Product name: ").strip()
        if not name:
            raise CLIError("Product name is required.")
        brand = ask("Brand (optional): ").strip()
        barcode = ask("Barcode (optional): ").strip()
        price = parse_price(ask("Price: ") or 0)
        stock = parse_stock(ask("Stock: ") or 0)
        return add_item(name, brand, barcode, price, stock)
    if choice == "4":
        item_id = parse_id(ask("Item id: "))
        price_in = ask("New price (blank to keep): ").strip()
        stock_in = ask("New stock (blank to keep): ").strip()
        price = parse_price(price_in) if price_in else None
        stock = parse_stock(stock_in) if stock_in else None
        return update_item(item_id, price=price, stock=stock)
    if choice == "5":
        item_id = parse_id(ask("Item id: "))
        if ask(f"Delete item {item_id}? (y/n): ").strip().lower() != "y":
            return "Delete cancelled."
        return delete_item(item_id)
    if choice == "6":
        mode = ask("Search by (1) barcode or (2) name? ").strip()
        if mode == "1":
            return find_external(barcode=ask("Barcode: ").strip())
        if mode == "2":
            return find_external(name=ask("Product name: ").strip())
        raise CLIError("Choose 1 or 2.")
    if choice == "7":
        barcode = ask("Barcode: ").strip()
        price = parse_price(ask("Price: ") or 0)
        stock = parse_stock(ask("Stock: ") or 0)
        return import_item(barcode, price, stock)
    raise CLIError("Invalid choice. Pick a number from the menu.")


def interactive_menu(ask=input, out=print):
    while True:
        out(MENU)
        choice = ask("Choose an option: ").strip()
        if choice == "0":
            out("Goodbye!")
            return
        try:
            out(run_menu_choice(choice, ask))
        except CLIError as exc:
            out(f"Error: {exc}")


# ---------- argparse entry point ----------

def build_parser():
    parser = argparse.ArgumentParser(description="Inventory Management CLI")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("list", help="List all items")
    p.add_argument("--name", help="Filter by product name")

    p = sub.add_parser("view", help="View one item")
    p.add_argument("id")

    p = sub.add_parser("add", help="Add a new item")
    p.add_argument("name")
    p.add_argument("--brand", default="")
    p.add_argument("--barcode", default="")
    p.add_argument("--price", default="0")
    p.add_argument("--stock", default="0")

    p = sub.add_parser("update", help="Update an item's price, stock or name")
    p.add_argument("id")
    p.add_argument("--price")
    p.add_argument("--stock")
    p.add_argument("--name")

    p = sub.add_parser("delete", help="Delete an item")
    p.add_argument("id")

    p = sub.add_parser("find", help="Find a product on OpenFoodFacts")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--barcode")
    group.add_argument("--name")

    p = sub.add_parser("import", help="Import a product from OpenFoodFacts into inventory")
    p.add_argument("barcode")
    p.add_argument("--price", default="0")
    p.add_argument("--stock", default="0")

    return parser


def run_command(args):
    """Dispatch parsed argparse arguments to a command and return its output."""
    if args.command == "list":
        return list_items(args.name)
    if args.command == "view":
        return view_item(parse_id(args.id))
    if args.command == "add":
        return add_item(args.name, args.brand, args.barcode, parse_price(args.price), parse_stock(args.stock))
    if args.command == "update":
        return update_item(
            parse_id(args.id),
            price=parse_price(args.price) if args.price is not None else None,
            stock=parse_stock(args.stock) if args.stock is not None else None,
            name=args.name,
        )
    if args.command == "delete":
        return delete_item(parse_id(args.id))
    if args.command == "find":
        return find_external(barcode=args.barcode, name=args.name)
    if args.command == "import":
        return import_item(args.barcode, parse_price(args.price), parse_stock(args.stock))
    raise CLIError(f"Unknown command: {args.command}")


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command is None:
        interactive_menu()
        return 0
    try:
        print(run_command(args))
        return 0
    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())