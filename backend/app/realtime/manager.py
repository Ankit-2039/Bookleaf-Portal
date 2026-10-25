import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger("bookleaf.realtime")
SEND_TIMEOUT = 2.0  # a stuck client must not stall everyone else


class ConnectionManager:
    """In-process registry of open sockets by channel ('admins', 'author:<id>').
    Single-process only: scaling out needs a shared pub/sub such as Redis."""

    def __init__(self) -> None:
        self._channels: dict[str, set] = defaultdict(set)

    def add(self, channel: str, ws) -> None:
        self._channels[channel].add(ws)

    def remove(self, channel: str, ws) -> None:
        sockets = self._channels.get(channel)
        if sockets is None:
            return
        sockets.discard(ws)
        if not sockets:
            del self._channels[channel]

    def count(self, channel: str) -> int:
        return len(self._channels.get(channel, ()))

    def total(self) -> int:
        return sum(len(s) for s in self._channels.values())

    async def send(self, channel: str, payload: dict) -> None:
        sockets = list(self._channels.get(channel, ()))
        if not sockets:
            return

        async def _one(ws):
            try:
                await asyncio.wait_for(ws.send_json(payload), SEND_TIMEOUT)
                return None
            except Exception:
                return ws  # dead or too slow

        for ws in await asyncio.gather(*(_one(w) for w in sockets)):
            if ws is not None:
                self.remove(channel, ws)


hub = ConnectionManager()