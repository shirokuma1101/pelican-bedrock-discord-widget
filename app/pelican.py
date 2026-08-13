from __future__ import annotations

from typing import Any

import aiohttp

from .models import PelicanServer, Resources


class PelicanAPIError(RuntimeError):
    pass


class PelicanClient:
    def __init__(
        self,
        base_url: str,
        server_id: str,
        token: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.server_id = server_id
        self.session = session
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "Application/vnd.pterodactyl.v1+json",
            "Content-Type": "application/json",
        }

    def url(self, suffix: str = "") -> str:
        return f"{self.base_url}/api/client/servers/{self.server_id}{suffix}"

    async def request(self, method: str, suffix: str = "", **kwargs: Any) -> Any:
        async with self.session.request(
            method,
            self.url(suffix),
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=8),
            **kwargs,
        ) as response:
            body = await response.text()

            if response.status >= 400:
                raise PelicanAPIError(
                    f"{response.status}: {body[:500]}"
                )

            if not body:
                return None

            try:
                return await response.json()
            except Exception:
                return body

    async def get_server(self) -> PelicanServer:
        payload = await self.request("GET")
        attr = payload.get("attributes", payload)
        limits = attr.get("limits") or {}

        return PelicanServer(
            identifier=attr.get("identifier", self.server_id),
            name=attr.get("name", self.server_id),
            state=attr.get("status") or attr.get("state") or "unknown",
            memory_limit_mb=positive_int(limits.get("memory")),
            cpu_limit=positive_float(limits.get("cpu")),
            disk_limit_mb=positive_int(limits.get("disk")),
        )

    async def get_resources(self) -> Resources:
        payload = await self.request("GET", "/resources")
        attr = payload.get("attributes", payload)
        resource = attr.get("resources", {})

        return Resources(
            current_state=attr.get("current_state", "unknown"),
            cpu_absolute=to_float(resource.get("cpu_absolute")),
            memory_bytes=to_int(resource.get("memory_bytes")),
            disk_bytes=to_int(resource.get("disk_bytes")),
        )

    async def power(self, signal: str) -> None:
        if signal not in {"start", "stop", "restart", "kill"}:
            raise ValueError(signal)

        await self.request(
            "POST",
            "/power",
            json={"signal": signal},
        )


def positive_int(value: Any) -> int | None:
    try:
        value = int(value)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def positive_float(value: Any) -> float | None:
    try:
        value = float(value)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
