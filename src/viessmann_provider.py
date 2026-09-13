import json
import os
from pathlib import Path
from typing import Any


class ViessmannProviderError(RuntimeError):
    """Raised when Viessmann data cannot be loaded."""


def _credentials() -> tuple[str, str, str, str]:
    username = os.getenv("VIESSMANN_USERNAME", "")
    password = os.getenv("VIESSMANN_PASSWORD", "")
    client_id = os.getenv("VIESSMANN_CLIENT_ID", "")
    token_file = os.getenv("VIESSMANN_TOKEN_FILE", "data/vicare_token.json")
    if not username or not password or not client_id:
        raise ViessmannProviderError(
            "Set VIESSMANN_USERNAME, VIESSMANN_PASSWORD, and VIESSMANN_CLIENT_ID locally."
        )
    return username, password, client_id, token_file


def load_client() -> Any:
    try:
        from PyViCare.PyViCare import PyViCare
    except ImportError as error:
        raise ViessmannProviderError("PyViCare is not installed") from error

    username, password, client_id, token_file = _credentials()
    client = PyViCare()
    try:
        client.initWithCredentials(username, password, client_id, token_file)
    except Exception as error:
        raise ViessmannProviderError(f"Viessmann authentication failed: {error}") from error
    return client


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def read_inventory(client: Any) -> list[dict[str, Any]]:
    inventory = []
    for device in getattr(client, "devices", []):
        try:
            raw_features = device.get_raw_json()
        except Exception as error:
            raw_features = {"error": type(error).__name__}
        inventory.append(
            {
                "id": str(device.getId()),
                "model": str(device.getModel()),
                "online": bool(device.isOnline()),
                "features": _safe_json(raw_features),
            }
        )
    if not inventory:
        raise ViessmannProviderError("No Viessmann devices were found")
    return inventory


def read_all_information() -> list[dict[str, Any]]:
    return read_inventory(load_client())
