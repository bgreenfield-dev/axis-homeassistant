"""Home Assistant's own test harness, for the entities and the config flow.

These need pytest-homeassistant-custom-component (requirements-test.txt); tests/test_client.py
runs without Home Assistant.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# custom_components/ on the path, as Home Assistant finds it in a config folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeClient:
    """Stands in for AxisClient: says hello with a room, records calls, answers set and press."""

    instances: list["FakeClient"] = []
    hello: dict[str, Any] = {}

    def __init__(self, session, url, token, on_live, on_connected) -> None:
        self.url = url
        self.token = token
        self.on_live = on_live
        self.on_connected = on_connected
        self.calls: list[tuple[str, dict]] = []
        self.watched: list[str] = []
        self.connected = True
        self.server_version = "0.19.7"
        FakeClient.instances.append(self)

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        self.connected = False

    async def watch(self, keys: list[str]) -> None:
        self.watched += keys

    async def call(self, method: str, params: dict | None = None) -> Any:
        self.calls.append((method, params or {}))
        if method == "rooms.haHello":
            return FakeClient.hello
        if method == "rooms.haSet":
            return {"values": {**ROOM_VALUES, params["key"]: params["value"]}}
        if method == "rooms.haPress":
            return {"values": ROOM_VALUES}
        return {}


ROOM = {
    "id": "bedroom",
    "name": "Bedroom",
    "area": "Bedroom",
    "entities": [
        {"platform": "select", "key": "scene", "name": "Scene", "options": ["Day", "Night"]},
        {"platform": "switch", "key": "lights", "name": "Lights"},
        {"platform": "number", "key": "hold", "name": "Hand hold", "min": 0, "max": 240, "unit": "min", "category": "config"},
        {"platform": "sensor", "key": "held", "name": "Lights held", "unit": "lights"},
        {"platform": "button", "key": "resume", "name": "Resume"},
    ],
}
ROOM_VALUES = {"scene": "Day", "lights": True, "hold": 30, "held": 1}


@pytest.fixture
def fake_axis():
    FakeClient.instances = []
    FakeClient.hello = {"protocol": 1, "app": "0.19.7", "rooms": [ROOM]}
    with patch("custom_components.axis_home.AxisClient", FakeClient):
        yield FakeClient
