"""Shared pytest fixtures."""

import pytest

from app import create_app
from data import reset_inventory


@pytest.fixture(autouse=True)
def fresh_inventory():
    """Reset the in-memory inventory before every test."""
    reset_inventory()
    yield
    reset_inventory()


@pytest.fixture
def client():
    """Flask test client for calling the API without a running server."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client