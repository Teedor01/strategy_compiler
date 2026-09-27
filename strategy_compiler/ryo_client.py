from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .envelope import RyoEnvelope, parse_envelope

RYO_TOOLS = {
    "market_overview": set(),
    "scan_market": {"chain", "theme", "top_n"},
    "analyze_token": {"symbol"},
    "deep_analysis": {"symbol", "include_perp"},
    "compare_tokens": {"symbols", "intent"},
    "monitor_market_sentiment_shift": {"time_window"},
}

REQUIRED_ARGS = {
    "analyze_token": {"symbol"},
    "deep_analysis": {"symbol"},
    "compare_tokens": {"symbols"},
}


class RyoToolError(Exception):
    """A tool call reached RYO but RYO reported an error (result.isError,
    or an HTTP error status per the guide's "REST errors include an HTTP
    status, stable code, message, and trace identifier" section).
    """

    def __init__(self, message: str, *, status_code: int | None = None, trace_id: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.trace_id = trace_id


class RyoConfigError(Exception):
    """RYO_MCP_URL / RYO_MCP_KEY missing or malformed."""


@dataclass(frozen=True)
class RyoClientConfig:
    base_url: str
    api_key: str
    timeout_s: float = 60.0
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "RyoClientConfig":
        base_url = os.environ.get("RYO_MCP_URL", "").rstrip("/")
        api_key = os.environ.get("RYO_MCP_KEY", "")
        if not base_url or not api_key:
            raise RyoConfigError(
                "RYO_MCP_URL and RYO_MCP_KEY must both be set (see .env.example). "
                "This build has neither configured in the current environment, "
                "so no live RYO call has been made or can be made here."
            )
        return cls(base_url=base_url, api_key=api_key)


class RyoClient:
    """Synchronous REST client. Matches the guide's Python REST example
    (`call_ryo(tool, arguments)`) but adds the retry/backoff behavior the
    same guide recommends in "Rate limits, retries, and errors":
    exponential backoff with jitter for 429/503/network errors, no retry
    on invalid-argument errors, honour Retry-After.
    """

    def __init__(self, config: RyoClientConfig | None = None, *, client: httpx.Client | None = None):
        self.config = config or RyoClientConfig.from_env()
        self._client = client or httpx.Client(timeout=self.config.timeout_s)

    def _validate_args(self, tool: str, arguments: dict[str, Any]) -> None:
        if tool not in RYO_TOOLS:
            raise RyoToolError(
                f"'{tool}' is not one of RYO's six published tools: {sorted(RYO_TOOLS)}. "
                "Refusing to call an invented tool name."
            )
        allowed = RYO_TOOLS[tool]
        unknown = set(arguments) - allowed
        if unknown:
            raise RyoToolError(f"{tool} does not accept argument(s) {sorted(unknown)}")
        missing = REQUIRED_ARGS.get(tool, set()) - set(arguments)
        if missing:
            raise RyoToolError(f"{tool} requires argument(s) {sorted(missing)}")

    def call(self, tool: str, arguments: dict[str, Any] | None = None) -> RyoEnvelope:
        """POST {base}/tools/{tool}/call with the bare argument object, per
        the guide's REST example. Retries per the guide's recommended policy.
        """
        arguments = arguments or {}
        self._validate_args(tool, arguments)

        url = f"{self.config.base_url}/tools/{tool}/call"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = self._client.post(url, headers=headers, json=arguments)
            except httpx.TransportError as exc:
                last_error = exc
                self._sleep_backoff(attempt, retry_after=None)
                continue

            if response.status_code == 429 or response.status_code == 503:
                retry_after = response.headers.get("Retry-After")
                last_error = RyoToolError(
                    f"RYO returned {response.status_code} for {tool}",
                    status_code=response.status_code,
                )
                self._sleep_backoff(attempt, retry_after=retry_after)
                continue

            if response.status_code >= 400:
                body = self._safe_json(response)
                raise RyoToolError(
                    f"RYO {response.status_code} calling {tool}: {body}",
                    status_code=response.status_code,
                    trace_id=(body or {}).get("trace_id") if isinstance(body, dict) else None,
                )

            body = response.json()
            return parse_envelope(body)

        raise RyoToolError(f"RYO call to {tool} failed after {self.config.max_retries} attempts") from last_error

    def _sleep_backoff(self, attempt: int, *, retry_after: str | None) -> None:
        if retry_after is not None:
            try:
                time.sleep(float(retry_after))
                return
            except ValueError:
                pass
        base = 0.5 * (2 ** attempt)
        time.sleep(base + random.uniform(0, base * 0.25))

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return {"raw_text": response.text}

    def close(self) -> None:
        self._client.close()


class FixtureRyoClient:
    """Replays a hand-built fixture envelope instead of calling RYO.

    Used only for local development and the parts of the test suite that
    exercise the resolver/evaluator against a realistic envelope shape
    without a live RYO_MCP_KEY. Every fixture file is labelled
    `"source": "fixture"` inside itself (see tests/fixtures/envelopes/) so
    nothing produced this way can be mistaken for a live RYO read... the
    label travels with the data into the receipt (see receipt.py), it is
    not just a comment in this file.
    """

    def __init__(self, envelopes: dict[str, RyoEnvelope]):
        self._envelopes = envelopes

    def call(self, tool: str, arguments: dict[str, Any] | None = None) -> RyoEnvelope:
        if tool not in RYO_TOOLS:
            raise RyoToolError(f"'{tool}' is not one of RYO's six published tools")
        if tool not in self._envelopes:
            raise RyoToolError(f"no fixture loaded for tool '{tool}'")
        return self._envelopes[tool]

    def close(self) -> None:
        pass
