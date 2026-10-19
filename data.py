"""
Mock database for the inventory system.

The inventory is a plain Python list (array) of dictionaries. Each item has
a unique "id" plus fields modelled on what the OpenFoodFacts API returns
(product_name, brands, ingredients_text, barcode, ...) and store-specific
fields (price, stock).
"""

import copy

# Seed data used to (re)initialise the inventory.
SEED_INVENTORY = [
    {
        "id": 1,
        "barcode": "0025293001169",
        "product_name": "Organic Almond Milk",
        "brands": "Silk",
        "ingredients_text": "Filtered water, almonds, cane sugar, sea salt, locust bean gum",
        "categories": "Plant-based milks",
        "price": 3.99,
        "stock": 25,
    },
    {
        "id": 2,
        "barcode": "3017620422003",
        "product_name": "Nutella",
        "brands": "Ferrero",
        "ingredients_text": "Sugar, palm oil, hazelnuts, skimmed milk powder, fat-reduced cocoa",
        "categories": "Spreads",
        "price": 5.49,
        "stock": 40,
    },
    {
        "id": 3,
        "barcode": "5449000000996",
        "product_name": "Coca-Cola",
        "brands": "Coca-Cola",
        "ingredients_text": "Carbonated water, sugar, colour (caramel E150d), phosphoric acid, natural flavourings, caffeine",
        "categories": "Sodas",
        "price": 1.25,
        "stock": 100,
    },
]

# The live, in-memory "database" that the API reads and writes.
inventory = copy.deepcopy(SEED_INVENTORY)


def reset_inventory():
    """Restore the inventory to its seed state (used by tests)."""
    inventory.clear()
    inventory.extend(copy.deepcopy(SEED_INVENTORY))


def next_id():
    """Return the next available item id."""
    return max((item["id"] for item in inventory), default=0) + 1


def find_item(item_id):
    """Return the item with the given id, or None if it does not exist."""
    return next((item for item in inventory if item["id"] == item_id), None)