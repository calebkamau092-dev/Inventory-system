# Design Document

## Task 1: Problem Definition

A small retail company needs an administrator portal so employees can manage inventory:

- **Create** new inventory items
- **Read** the full inventory or a single item
- **Update** item prices and stock levels
- **Delete** discontinued items
- **Enrich** products with real data from the [OpenFoodFacts](https://world.openfoodfacts.org) API (lookup by barcode or name)

Constraints: data is stored in an in-memory Python list that simulates a database. Employees use a command-line interface (CLI) that talks to a Flask REST API over HTTP.

## Task 2: Design

### Architecture

```
 ┌──────────┐   HTTP/JSON   ┌──────────────┐   reads/writes  ┌───────────────────┐
 │  cli.py  │ ────────────► │    app.py    │ ──────────────► │ data.py           │
 │ (user)   │ ◄──────────── │  Flask API   │                 │ inventory = [...] │
 └──────────┘               └──────┬───────┘                 └───────────────────┘
                                   │ HTTPS (requests)
                                   ▼
                           ┌──────────────────┐
                           │ external_api.py  │ ──► OpenFoodFacts API
                           └──────────────────┘
```

### Data model

Every item in the `inventory` array follows this shape, modelled on the OpenFoodFacts `product` object plus store fields:

| Field              | Type   | Source          | Notes                     |
|--------------------|--------|-----------------|---------------------------|
| `id`               | int    | generated       | unique, auto-incremented  |
| `barcode`          | string | OpenFoodFacts   | `code` in OFF responses   |
| `product_name`     | string | OpenFoodFacts   | required                  |
| `brands`           | string | OpenFoodFacts   |                           |
| `ingredients_text` | string | OpenFoodFacts   |                           |
| `categories`       | string | OpenFoodFacts   |                           |
| `price`            | float  | store           | must be ≥ 0               |
| `stock`            | int    | store           | must be ≥ 0               |

### Route plan

| Route | Input | Output | Effect on data | Triggered by CLI |
|-------|-------|--------|----------------|------------------|
| `GET /inventory` | optional `?name=` | `200` list of items | none | menu **1** / `list` |
| `GET /inventory/<id>` | id in URL | `200` item, or `404` | none | menu **2** / `view` |
| `POST /inventory` | JSON with `product_name` (required), optional fields | `201` new item, or `400` | appends an item | menu **3** / `add` |
| `PATCH /inventory/<id>` | JSON with any editable fields | `200` updated item, or `400`/`404` | updates fields in place | menu **4** / `update` |
| `DELETE /inventory/<id>` | id in URL | `200` message + deleted item, or `404` | removes the item | menu **5** / `delete` |
| `GET /external/product/<barcode>` | barcode in URL | `200` product, or `400`/`404`/`502` | none | menu **6** / `find --barcode` |
| `GET /external/search?name=` | `name` query | `200` list of products, or `400`/`502` | none | menu **6** / `find --name` |
| `POST /inventory/import` | JSON `{barcode, price?, stock?}` | `201` new item, or `400`/`404`/`409`/`502` | appends an item built from OFF data | menu **7** / `import` |

### Error handling

- Invalid input (bad JSON, negative price, non-integer stock, unknown fields) → `400`
- Missing item → `404`
- Duplicate barcode on import → `409`
- OpenFoodFacts unreachable / server error / bad JSON → `502`
- The CLI validates input before sending and turns any API error into a readable `Error: ...` message instead of crashing.

## Git workflow

Each feature was built on its own branch, merged into `main` through a GitHub pull request, then deleted:

1. `feature/api-crud`: Flask CRUD routes + endpoint tests
2. `feature/external-api`: OpenFoodFacts client, helper routes + mocked tests
3. `feature/cli`: CLI + CLI tests
4. `docs/readme`: README and this design document