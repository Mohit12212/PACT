"""WebSocket fan-out: pushes notifications and chat messages to every open tab of a user."""
from collections import defaultdict

from fastapi import WebSocket


class Hub:
    def __init__(self):
        self.conns: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self.conns[user_id].add(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        self.conns[user_id].discard(ws)

    async def push(self, user_ids, event: dict):
        for uid in set(user_ids):
            for ws in list(self.conns.get(uid, ())):
                try:
                    await ws.send_json(event)
                except Exception:
                    self.conns[uid].discard(ws)


hub = Hub()
