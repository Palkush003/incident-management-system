"""
WebSocket Connection Manager — Observer Pattern.
Broadcasts real-time events to all connected frontend clients.
"""
import asyncio
import json
from typing import Any
from fastapi import WebSocket
import structlog

log = structlog.get_logger(__name__)


class WebSocketManager:
    """
    Manages all active WebSocket connections.
    Implements Observer pattern: publishes events to all subscribers.
    """

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        log.info("ws.client_connected", total=len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        log.info("ws.client_disconnected", total=len(self._connections))

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send a JSON message to all connected clients."""
        if not self._connections:
            return
        message = json.dumps(data, default=str)
        dead_connections: set[WebSocket] = set()

        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.add(ws)

        if dead_connections:
            async with self._lock:
                self._connections -= dead_connections

    async def send_to(self, ws: WebSocket, data: dict[str, Any]) -> None:
        """Send a message to a specific client."""
        try:
            await ws.send_text(json.dumps(data, default=str))
        except Exception as exc:
            log.warning("ws.send_failed", error=str(exc))
            await self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Global singleton
ws_manager = WebSocketManager()
