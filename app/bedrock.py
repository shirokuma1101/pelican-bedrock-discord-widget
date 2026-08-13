from __future__ import annotations

import asyncio

from mcstatus import BedrockServer

from .models import BedrockStatus


class BedrockClient:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    async def status(self) -> BedrockStatus:
        return await asyncio.to_thread(self._status_sync)

    def _status_sync(self) -> BedrockStatus:
        try:
            server = BedrockServer.lookup(f"{self.host}:{self.port}")
            result = server.status()

            motd = result.motd.to_plain()
            return BedrockStatus(
                online=True,
                latency_ms=float(result.latency),
                version=result.version.name,
                motd=motd.replace("\n", " ").strip(),
                online_players=result.players.online,
                max_players=result.players.max,
            )
        except Exception:
            return BedrockStatus(online=False)
