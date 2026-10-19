# Inventory Management System

A Flask REST API and command-line interface (CLI) that lets retail employees add, view, update and delete inventory items. It integrates the [OpenFoodFacts API](https://world.openfoodfacts.org) to look up real product details by barcode or name and import them into inventory.

## Features

- Full CRUD on inventory via a RESTful Flask API (stored in an in-memory list)
- OpenFoodFacts lookup by **barcode** or **product name**
- One-step **import** of an OpenFoodFacts product into inventory
- CLI with an interactive menu *and* one-off subcommands
- Input validation and friendly error messages (invalid input, missing items, API failures)
- 73 pytest tests using `unittest.mock` to simulate HTTP responses

## Project Structure

```
inventory-system/
├── app.py              # Flask app: CRUD + OpenFoodFacts helper routes
├── data.py             # In-memory inventory array (mock database)
├── external_api.py     # OpenFoodFacts API client
├── cli.py              # Command-line interface
├── requirements.txt
├── docs/
│   └── design.md       # Problem definition, route plan, architecture
└── tests/
    ├── conftest.py           # Shared fixtures (test client, data reset)
    ├── test_api.py           # CRUD endpoint tests
    ├── test_external_api.py  # OpenFoodFacts client + helper route tests
    └── test_cli.py           # CLI command tests
```

## Installation and Setup

Requires Python 3.10+.

```bash
git clone https://github.com/calebkamau092-dev/Inventory-system.git
cd Inventory-system

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Run the API

```bash
python app.py
```

The server starts at `http://127.0.0.1:5000` in Flask debug mode (auto-reload, detailed error pages).

### Run the CLI

Open a **second terminal** (keep the server running), activate the venv, then:

```bash
python cli.py
```

To point the CLI at a different server, set `INVENTORY_API_URL`, e.g. `export INVENTORY_API_URL=http://localhost:8000`.

### Run the tests

```bash
pytest -v
```

The tests don't need the server running or internet access, because all HTTP calls are mocked.

## API Endpoints

### Inventory (CRUD)

| Method | Endpoint | Description | Success | Errors |
|--------|----------|-------------|---------|--------|
| GET | `/inventory` | List all items. Optional `?name=` filter | 200 | |
| GET | `/inventory/<id>` | Get one item | 200 | 404 |
| POST | `/inventory` | Add an item (`product_name` required) | 201 | 400 |
| PATCH | `/inventory/<id>` | Update one or more fields | 200 | 400, 404 |
| DELETE | `/inventory/<id>` | Delete an item | 200 | 404 |

### OpenFoodFacts helpers

| Method | Endpoint | Description | Success | Errors |
|--------|----------|-------------|---------|--------|
| GET | `/external/product/<barcode>` | Look up a product by barcode | 200 | 400, 404, 502 |
| GET | `/external/search?name=<term>` | Search products by name | 200 | 400, 502 |
| POST | `/inventory/import` | Fetch a product by barcode and add it to inventory | 201 | 400, 404, 409, 502 |

### Item format

```json
{
  "id": 1,
  "barcode": "0025293001169",
  "product_name": "Organic Almond Milk",
  "brands": "Silk",
  "ingredients_text": "Filtered water, almonds, cane sugar, sea salt, locust bean gum",
  "categories": "Plant-based milks",
  "price": 3.99,
  "stock": 25
}
```

Editable fields: `barcode`, `product_name`, `brands`, `ingredients_text`, `categories`, `price` (number ≥ 0), `stock` (integer ≥ 0). The `id` is assigned by the server and cannot be changed.

### Example requests (curl / Postman)

```bash
# List everything
curl http://127.0.0.1:5000/inventory

# Add an item
curl -X POST http://127.0.0.1:5000/inventory \
  -H "Content-Type: application/json" \
  -d '{"product_name": "Brown Bread", "brands": "Festive", "price": 0.99, "stock": 10}'

# Update price and stock
curl -X PATCH http://127.0.0.1:5000/inventory/1 \
  -H "Content-Type: application/json" \
  -d '{"price": 4.25, "stock": 30}'

# Delete
curl -X DELETE http://127.0.0.1:5000/inventory/1

# Import Nutella from OpenFoodFacts
curl -X POST http://127.0.0.1:5000/inventory/import \
  -H "Content-Type: application/json" \
  -d '{"barcode": "3017620422003", "price": 5.49, "stock": 20}'
```

Errors are always returned as JSON: `{"error": "Item 99 not found"}`.

## CLI Usage

### Interactive menu

```
$ python cli.py

===== Inventory Management =====
1. List all items
2. View item details
3. Add new item
4. Update item price / stock
5. Delete item
6. Find product on OpenFoodFacts
7. Import product from OpenFoodFacts
0. Exit

Choose an option: 1
[1] Organic Almond Milk | $3.99 | stock: 25
[2] Nutella | $5.49 | stock: 40
[3] Coca-Cola | $1.25 | stock: 100
```

### One-off commands

```bash
python cli.py list
python cli.py list --name milk
python cli.py view 1
python cli.py add "Brown Bread" --brand Festive --price 0.99 --stock 10
python cli.py update 1 --price 4.25 --stock 30
python cli.py delete 4
python cli.py find --barcode 3017620422003
python cli.py find --name "almond milk"
python cli.py import 3017620422003 --price 5.49 --stock 20
python cli.py --help
```

Example output:

```
$ python cli.py add "Brown Bread" --brand Festive --price 0.99 --stock 10
Item added:
[4] Brown Bread
    Brand:       Festive
    Barcode:     -
    Category:    -
    Price:       $0.99
    Stock:       10

$ python cli.py update 1 --price abc
Error: Invalid price: 'abc'. Enter a number like 2.99.

$ python cli.py view 99
Error: Item 99 not found
```

## Notes and Limitations

- Data lives in memory, so it resets to the three seed items every time the server restarts.
- OpenFoodFacts is a free, community-maintained database. Some products have missing fields, and the name-search endpoint is sometimes overloaded (the API then returns a 502 error).

See [`docs/design.md`](docs/design.md) for the problem definition, route planning and architecture.