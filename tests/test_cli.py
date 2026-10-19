"""
Tests for the CLI (cli.py).

HTTP calls to the Flask API are mocked with unittest.mock, so the server
does not need to be running.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

import cli
from cli import CLIError

SAMPLE_ITEM = {
    "id": 1,
    "barcode": "0025293001169",
    "product_name": "Organic Almond Milk",
    "brands": "Silk",
    "ingredients_text": "Filtered water, almonds",
    "categories": "Plant-based milks",
    "price": 3.99,
    "stock": 25,
}


def mock_response(status_code=200, json_data=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    return response


# ---------- api_request ----------

@patch("cli.requests.request")
def test_api_request_returns_json(mock_request):
    mock_request.return_value = mock_response(200, [SAMPLE_ITEM])
    assert cli.api_request("GET", "/inventory") == [SAMPLE_ITEM]


@patch("cli.requests.request")
def test_api_request_raises_on_api_error(mock_request):
    mock_request.return_value = mock_response(404, {"error": "Item 9 not found"})
    with pytest.raises(CLIError, match="Item 9 not found"):
        cli.api_request("GET", "/inventory/9")


@patch("cli.requests.request", side_effect=requests.ConnectionError())
def test_api_request_server_down(mock_request):
    with pytest.raises(CLIError, match="Cannot connect"):
        cli.api_request("GET", "/inventory")


@patch("cli.requests.request", side_effect=requests.Timeout())
def test_api_request_timeout(mock_request):
    with pytest.raises(CLIError, match="too long"):
        cli.api_request("GET", "/inventory")


# ---------- Commands ----------

@patch("cli.api_request")
def test_list_items(mock_api):
    mock_api.return_value = [SAMPLE_ITEM]
    output = cli.list_items()
    assert "Organic Almond Milk" in output
    assert "$3.99" in output
    mock_api.assert_called_once_with("GET", "/inventory", params=None)


@patch("cli.api_request", return_value=[])
def test_list_items_empty(mock_api):
    assert cli.list_items() == "No items found."


@patch("cli.api_request", return_value=SAMPLE_ITEM)
def test_view_item(mock_api):
    output = cli.view_item(1)
    assert "Silk" in output
    assert "Filtered water" in output
    mock_api.assert_called_once_with("GET", "/inventory/1")


@patch("cli.api_request", return_value=SAMPLE_ITEM)
def test_add_item_sends_post(mock_api):
    output = cli.add_item("Organic Almond Milk", "Silk", "", 3.99, 25)
    assert "Item added" in output
    method, path = mock_api.call_args[0]
    assert (method, path) == ("POST", "/inventory")
    assert mock_api.call_args[1]["json"]["price"] == 3.99


@patch("cli.api_request", return_value={**SAMPLE_ITEM, "price": 4.5})
def test_update_item_sends_only_changed_fields(mock_api):
    output = cli.update_item(1, price=4.5)
    assert "$4.50" in output
    mock_api.assert_called_once_with("PATCH", "/inventory/1", json={"price": 4.5})


def test_update_item_requires_a_field():
    with pytest.raises(CLIError, match="Nothing to update"):
        cli.update_item(1)


@patch("cli.api_request", return_value={"message": "Item 1 deleted"})
def test_delete_item(mock_api):
    assert cli.delete_item(1) == "Item 1 deleted"
    mock_api.assert_called_once_with("DELETE", "/inventory/1")


@patch("cli.api_request")
def test_find_external_by_barcode(mock_api):
    mock_api.return_value = {"barcode": "123", "product_name": "Nutella", "brands": "Ferrero"}
    output = cli.find_external(barcode="123")
    assert "Nutella - Ferrero" in output
    mock_api.assert_called_once_with("GET", "/external/product/123")


@patch("cli.api_request")
def test_find_external_by_name(mock_api):
    mock_api.return_value = [{"barcode": "1", "product_name": "Oat Milk", "brands": "Oatly"}]
    output = cli.find_external(name="oat")
    assert "1. Oat Milk - Oatly" in output


@patch("cli.api_request", return_value=[])
def test_find_external_no_results(mock_api):
    assert "No products found" in cli.find_external(name="zzz")


def test_find_external_requires_input():
    with pytest.raises(CLIError):
        cli.find_external()


@patch("cli.api_request", return_value=SAMPLE_ITEM)
def test_import_item(mock_api):
    output = cli.import_item("0025293001169", 3.99, 25)
    assert "Imported from OpenFoodFacts" in output
    mock_api.assert_called_once_with(
        "POST", "/inventory/import", json={"barcode": "0025293001169", "price": 3.99, "stock": 25}
    )


# ---------- Input validation ----------

@pytest.mark.parametrize("value", ["abc", "-1", None])
def test_parse_price_invalid(value):
    with pytest.raises(CLIError):
        cli.parse_price(value)


def test_parse_price_valid():
    assert cli.parse_price("2.999") == 3.0


@pytest.mark.parametrize("value", ["1.5", "-3", "ten"])
def test_parse_stock_invalid(value):
    with pytest.raises(CLIError):
        cli.parse_stock(value)


@pytest.mark.parametrize("value", ["0", "x", "-2"])
def test_parse_id_invalid(value):
    with pytest.raises(CLIError):
        cli.parse_id(value)


# ---------- Interactive menu ----------

def fake_input(*answers):
    """Return an input() replacement that yields the given answers in order."""
    it = iter(answers)
    return lambda prompt="": next(it)


@patch("cli.update_item", return_value="updated")
def test_menu_update_with_blank_stock(mock_update):
    result = cli.run_menu_choice("4", fake_input("1", "4.25", ""))
    assert result == "updated"
    mock_update.assert_called_once_with(1, price=4.25, stock=None)


@patch("cli.delete_item")
def test_menu_delete_can_be_cancelled(mock_delete):
    result = cli.run_menu_choice("5", fake_input("2", "n"))
    assert result == "Delete cancelled."
    mock_delete.assert_not_called()


def test_menu_add_requires_name():
    with pytest.raises(CLIError, match="required"):
        cli.run_menu_choice("3", fake_input(""))


def test_menu_invalid_choice():
    with pytest.raises(CLIError, match="Invalid choice"):
        cli.run_menu_choice("42", fake_input())


@patch("cli.list_items", return_value="the list")
def test_interactive_menu_shows_errors_and_exits(mock_list):
    printed = []
    cli.interactive_menu(ask=fake_input("1", "9", "0"), out=printed.append)
    assert "the list" in printed
    assert any("Invalid choice" in line for line in printed)
    assert printed[-1] == "Goodbye!"


# ---------- argparse entry point ----------

@patch("cli.api_request", return_value={**SAMPLE_ITEM, "stock": 30})
def test_main_update_command(mock_api, capsys):
    exit_code = cli.main(["update", "1", "--stock", "30"])
    assert exit_code == 0
    assert "Stock:       30" in capsys.readouterr().out
    mock_api.assert_called_once_with("PATCH", "/inventory/1", json={"stock": 30})


def test_main_reports_invalid_input(capsys):
    exit_code = cli.main(["add", "Bread", "--price", "cheap"])
    assert exit_code == 1
    assert "Invalid price" in capsys.readouterr().err


@patch("cli.api_request", side_effect=CLIError("Item 99 not found"))
def test_main_reports_api_errors(mock_api, capsys):
    assert cli.main(["view", "99"]) == 1
    assert "Item 99 not found" in capsys.readouterr().err


# ---------- Low stock report ----------

@patch("cli.api_request", return_value=[SAMPLE_ITEM])
def test_low_stock(mock_api):
    output = cli.low_stock(30)
    assert "Organic Almond Milk | stock: 25" in output
    mock_api.assert_called_once_with("GET", "/inventory/low-stock", params={"threshold": 30})


@patch("cli.api_request", return_value=[])
def test_low_stock_empty(mock_api):
    assert "No items" in cli.low_stock(5)


@patch("cli.low_stock", return_value="report")
def test_menu_low_stock_uses_default(mock_low):
    assert cli.run_menu_choice("8", fake_input("")) == "report"
    mock_low.assert_called_once_with(10)


def test_main_low_stock_rejects_bad_threshold(capsys):
    assert cli.main(["low-stock", "--threshold", "lots"]) == 1