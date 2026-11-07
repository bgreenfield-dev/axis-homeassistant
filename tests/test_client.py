"""The Axis socket client against a small stand-in for the Axis hub."""

import asyncio
import json
import sys
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "axis_home"))
# client.py imports .const; load both as a package without Home Assistant.
import importlib.util  # noqa: E402

pkg = Path(__file__).resolve().parents[1] / "custom_components" / "axis_home"
spec = importlib.util.spec_from_file_location("axis_home_pkg", pkg / "__init__.py")
sys.modules["axis_home_pkg"] = importlib.util.module_from_spec(spec)
sys.modules["axis_home_pkg"].__path__ = [str(pkg)]
const = importlib.import_module("axis_home_pkg.const")
client_mod = importlib.import_module("axis_home_pkg.client")


class FakeHub:
    def __init__(self):
        self.hellos = []
        self.codes = {"ABCD2345"}
        self.tokens = set()
        self.sockets = []

    async def handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.sockets.append(ws)
        async for msg in ws:
            data = json.loads(msg.data)
            if data["type"] == "hello":
                self.hellos.append(data)
                auth = data["auth"]
                if auth.get("pairingCode") in self.codes:
                    self.codes.discard(auth["pairingCode"])
                    self.tokens.add("tok")
                    await ws.send_json({"type": "welcome", "token": "tok", "app": "0.19.5"})
                elif auth.get("token") in self.tokens:
                    await ws.send_json({"type": "welcome", "token": "tok", "app": "0.19.5"})
                else:
                    await ws.send_json({"type": "denied", "reason": "wrong or expired"})
                    await ws.close()
            elif data["type"] == "request":
                if data["method"] == "rooms.haHello":
                    await ws.send_json(
                        {"type": "response", "id": data["id"], "ok": True, "result": {"protocol": 1}}
                    )
                else:
                    await ws.send_json(
                        {"type": "response", "id": data["id"], "ok": False, "error": "no"}
                    )
            elif data["type"] == "live.watch":
                for key in data["keys"]:
                    await ws.send_json({"type": "live", "key": key, "data": {"rev": "r1"}})
        return ws


@pytest.fixture
async def hub(aiohttp_unused_port=None):
    fake = FakeHub()
    app = web.Application()
    app.router.add_get("/ws", fake.handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    fake.url = f"http://127.0.0.1:{port}"
    yield fake
    await runner.cleanup()


def test_ws_url():
    assert client_mod.ws_url("http://10.0.0.5:7337/") == "ws://10.0.0.5:7337/ws"
    assert client_mod.ws_url("https://axis.example.com") == "wss://axis.example.com/ws"
    with pytest.raises(client_mod.AxisError):
        client_mod.ws_url("10.0.0.5")


async def test_pairs_once_as_home_assistant(hub):
    async with aiohttp.ClientSession() as session:
        token = await client_mod.pair(session, hub.url, "abcd2345")
        assert token == "tok"
        hello = hub.hellos[0]
        assert hello["agent"]["kind"] == "homeassistant"
        assert hello["version"] == const.SOCKET_PROTOCOL and hello["role"] == "ui"
        with pytest.raises(client_mod.AxisAuthError):
            await client_mod.pair(session, hub.url, "ABCD2345")


async def test_calls_watches_and_reconnects(hub, monkeypatch):
    monkeypatch.setattr(client_mod, "RETRY_DELAYS", (0.05,))
    hub.tokens.add("tok")
    live = []
    states = []
    async with aiohttp.ClientSession() as session:
        c = client_mod.AxisClient(
            session, hub.url, "tok", lambda k, d: live.append(k), lambda on: states.append(on)
        )
        await c.start()
        assert (await c.call("rooms.haHello"))["protocol"] == 1
        with pytest.raises(client_mod.AxisError):
            await c.call("rooms.list")
        await c.watch(["rooms-ha:bedroom"])
        for _ in range(50):
            if live:
                break
            await asyncio.sleep(0.02)
        assert live == ["rooms-ha:bedroom"]
        # The hub drops it: it comes back and watches again.
        await hub.sockets[-1].close()
        for _ in range(100):
            if len(live) >= 2:
                break
            await asyncio.sleep(0.02)
        assert live == ["rooms-ha:bedroom", "rooms-ha:bedroom"]
        assert states[:3] == [True, False, True]
        await c.close()
