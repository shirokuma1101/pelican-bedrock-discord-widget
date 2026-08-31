from __future__ import annotations

import re
from typing import Any

import aiohttp


class VictoriaMetricsClient:
    def __init__(
        self,
        url: str,
        query: str,
        average_window: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self.url = url
        self.query = query
        if not re.fullmatch(r"[1-9]\d*[smhdwy]", average_window):
            raise ValueError(f"Invalid POWER_AVERAGE_WINDOW: {average_window}")
        self.average_window = average_window
        self.session = session

    async def get_cpu_watts(self) -> float:
        async with self.session.get(
            self.url,
            params={
                "query": f"avg_over_time({self.query}[{self.average_window}])"
            },
            timeout=aiohttp.ClientTimeout(total=8),
        ) as response:
            response.raise_for_status()
            payload: Any = await response.json()

        return parse_current_value(payload)


def parse_current_value(payload: Any) -> float:
    if not isinstance(payload, dict):
        raise RuntimeError("query returned an invalid response")
    if payload.get("status") != "success":
        raise RuntimeError(f"query failed: {payload.get('error', 'unknown error')}")
    results = payload.get("data", {}).get("result", [])
    if not results:
        raise RuntimeError("query returned no time series")
    value = results[0].get("value", [])
    if len(value) < 2:
        raise RuntimeError("query returned no current value")
    try:
        return float(value[1])
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid metric value: {value[1]!r}") from exc
