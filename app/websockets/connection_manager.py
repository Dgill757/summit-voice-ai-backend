"""
WebSocket Connection Manager
Manages real-time connections and broadcasts updates
"""
from __future__ import annotations

from typing import Dict, List, Set
from datetime import datetime
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscribers: Dict[str, Set[WebSocket]] = {
            "agent_execution": set(),
            "lead_created": set(),
            "content_approved": set(),
            "metrics_updated": set(),
            "all": set(),
        }

    async def connect(self, websocket: WebSocket, subscribe_to: List[str] | None = None):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

        if subscribe_to:
            for event_type in subscribe_to:
                if event_type in self.subscribers:
                    self.subscribers[event_type].add(websocket)
        else:
            self.subscribers["all"].add(websocket)

        await websocket.send_json(
            {
                "type": "connection_established",
                "message": "Connected to Summit AI real-time updates",
                "subscriptions": subscribe_to or ["all"],
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for subscribers in self.subscribers.values():
            subscribers.discard(websocket)

    async def broadcast(self, event_type: str, data: dict):
        """Broadcast event to all subscribed connections."""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        recipients = self.subscribers.get(event_type, set()) | self.subscribers.get("all", set())
        disconnected: List[WebSocket] = []
        for connection in recipients:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection)

    async def send_personal(self, websocket: WebSocket, event_type: str, data: dict):
        """Send message to specific connection."""
        try:
            await websocket.send_json(
                {
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        except Exception:
            self.disconnect(websocket)


manager = ConnectionManager()

