"""
WebSocket API Endpoints
Real-time updates for dashboard
"""
from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from typing import List
import json

from app.websockets.connection_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    subscribe: List[str] = Query(default=["all"]),
):
    """
    WebSocket endpoint for real-time updates.

    Example:
      ws://localhost:8000/ws?subscribe=agent_execution&subscribe=lead_created
    """
    await manager.connect(websocket, subscribe)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal(websocket, "pong", {"status": "alive"})
            except json.JSONDecodeError:
                continue
    except WebSocketDisconnect:
        manager.disconnect(websocket)

