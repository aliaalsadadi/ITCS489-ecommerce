from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class AuctionWsManager:
    def __init__(self) -> None:
        self._rooms: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, auction_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms[auction_id].add(websocket)

    async def disconnect(self, auction_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(auction_id)
            if not room:
                return
            room.discard(websocket)
            if not room:
                self._rooms.pop(auction_id, None)

    async def broadcast(self, auction_id: UUID, payload: dict) -> None:
        room = list(self._rooms.get(auction_id, set()))
        if not room:
            return

        stale: list[WebSocket] = []
        for ws in room:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)

        if stale:
            async with self._lock:
                room_set = self._rooms.get(auction_id)
                if not room_set:
                    return
                for ws in stale:
                    room_set.discard(ws)
                if not room_set:
                    self._rooms.pop(auction_id, None)


auction_ws_manager = AuctionWsManager()
