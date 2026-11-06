"""The Axis server's socket, as Axis Home uses it.

Axis Home signs in to the Axis hub as Home Assistant: a login that may only call
rooms.haHello, rooms.haSet and rooms.haPress and watch "rooms-ha:<room>" values.
This module knows nothing about Home Assistant, so it is tested on its own.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .const import SERVER_DEVICE, SOCKET_PROTOCOL, VERSION

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20
# Reconnect waits, in seconds, the last repeated.
RETRY_DELAYS = (1, 2, 5, 10, 30, 60)


class AxisError(Exception):
    """Axis answered with an error, or couldn't be reached."""


class AxisAuthError(AxisError):
    """Axis turned the login away: a wrong or used code, or a revoked login."""


def ws_url(url: str) -> str:
    """http://10.0.0.5:7337 as ws://10.0.0.5:7337/ws."""
    base = url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/ws"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/ws"
    raise AxisError(f"{url} isn't an http(s) address")


def hello(auth: dict[str, str]) -> dict[str, Any]:
    """The hub's hello for Home Assistant's login."""
    return {
        "type": "hello",
        "version": SOCKET_PROTOCOL,
        "app": f"axis_home/{VERSION}",
        "role": "ui",
        "auth": auth,
        "agent": {"kind": "homeassistant", "name": "Home Assistant"},
    }


async def pair(session: aiohttp.ClientSession, url: str, code: str) -> str:
    """Signs in once with a pairing code and answers the saved login (token)."""
    welcome = await _sign_in(session, url, {"pairingCode": code.strip().upper()})
    token = welcome.get("token")
    if not isinstance(token, str) or not token:
        raise AxisAuthError("Axis gave no login")
    return token


async def _sign_in(
    session: aiohttp.ClientSession, url: str, auth: dict[str, str]
) -> dict[str, Any]:
    try:
        async with session.ws_connect(ws_url(url), heartbeat=30, timeout=aiohttp.ClientWSTimeout(ws_close=15)) as ws:
            await ws.send_json(hello(auth))
            msg = await ws.receive(timeout=15)
            if msg.type != aiohttp.WSMsgType.TEXT:
                raise AxisError("Axis closed the connection")
            data = json.loads(msg.data)
            if data.get("type") == "denied":
                raise AxisAuthError(str(data.get("reason", "Axis said no")))
            if data.get("type") != "welcome":
                raise AxisError("Axis didn't welcome the login")
            return data
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise AxisError(f"Can't reach Axis at {url}: {err}") from err


class AxisClient:
    """A lasting connection: requests, live values, and reconnecting when it drops."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        token: str,
        on_live: Callable[[str, Any], None],
        on_connected: Callable[[bool], Awaitable[None] | None] | None = None,
    ) -> None:
        self._session = session
        self._url = url
        self._token = token
        self._on_live = on_live
        self._on_connected = on_connected
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ids = itertools.count(1)
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._watching: list[str] = []
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._closing = False
        self.connected = False
        self.server_version: str | None = None

    async def start(self) -> None:
        """Connects once (raising if it can't), then keeps the connection up."""
        await self._connect()
        self._task = asyncio.create_task(self._run())

    async def close(self) -> None:
        self._closing = True
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._fail_pending(AxisError("Closed"))

    async def _connect(self) -> None:
        try:
            ws = await self._session.ws_connect(ws_url(self._url), heartbeat=30, timeout=aiohttp.ClientWSTimeout(ws_close=15))
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise AxisError(f"Can't reach Axis at {self._url}: {err}") from err
        await ws.send_json(hello({"token": self._token}))
        msg = await ws.receive(timeout=15)
        data = json.loads(msg.data) if msg.type == aiohttp.WSMsgType.TEXT else {}
        if data.get("type") == "denied":
            await ws.close()
            raise AxisAuthError(str(data.get("reason", "Axis said no")))
        if data.get("type") != "welcome":
            await ws.close()
            raise AxisError("Axis didn't welcome the login")
        self.server_version = data.get("app")
        self._ws = ws
        self._ready.set()
        await self._set_connected(True)
        if self._watching:
            await ws.send_json({"type": "live.watch", "keys": self._watching})

    async def _set_connected(self, on: bool) -> None:
        self.connected = on
        if self._on_connected:
            result = self._on_connected(on)
            if asyncio.iscoroutine(result):
                await result

    async def _run(self) -> None:
        attempt = 0
        while not self._closing:
            if self._ws is None:
                try:
                    await self._connect()
                    attempt = 0
                except AxisAuthError as err:
                    _LOGGER.error("Axis turned the login away: %s", err)
                    return
                except AxisError as err:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    attempt += 1
                    _LOGGER.debug("Axis unreachable (%s); again in %ss", err, delay)
                    await asyncio.sleep(delay)
                    continue
            ws = self._ws
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    self._receive(json.loads(msg.data))
                except Exception:  # noqa: BLE001 - one bad message mustn't drop the link
                    _LOGGER.exception("Couldn't handle a message from Axis")
            self._ws = None
            self._ready.clear()
            self._fail_pending(AxisError("Axis went away"))
            await self._set_connected(False)

    def _receive(self, data: dict[str, Any]) -> None:
        kind = data.get("type")
        if kind == "response":
            fut = self._pending.pop(str(data.get("id")), None)
            if fut and not fut.done():
                if data.get("ok"):
                    fut.set_result(data.get("result"))
                else:
                    fut.set_exception(AxisError(str(data.get("error", "Axis said no"))))
        elif kind == "live":
            self._on_live(str(data.get("key")), data.get("data"))

    def _fail_pending(self, err: Exception) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Calls a server method and answers its result."""
        if self._ws is None:
            raise AxisError("Not connected to Axis")
        rid = f"ha{next(self._ids)}"
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        await self._ws.send_json(
            {
                "type": "request",
                "id": rid,
                "device": SERVER_DEVICE,
                "method": method,
                "params": params or {},
            }
        )
        try:
            return await asyncio.wait_for(fut, REQUEST_TIMEOUT)
        finally:
            self._pending.pop(rid, None)

    async def watch(self, keys: list[str]) -> None:
        """The whole set of live values to follow; kept across reconnects."""
        self._watching = list(keys)
        if self._ws is not None:
            await self._ws.send_json({"type": "live.watch", "keys": self._watching})
