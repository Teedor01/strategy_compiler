"""RYO builder client -- REST transport.

Implemented directly against docs/MCP-Builder-Guide.md (RYO's own guide,
"Last updated: August 13, 2026", endpoint https://app-ryochan.com/api/mcp,
protocol version 2024-11-05). Not tested against the live service in this
environment: this build has no RYO_MCP_KEY. See docs/LIMITATIONS.md for
exactly what that means and does not mean.

The six tools and their required/optional arguments are taken verbatim from
the guide's tool table:

    market_overview                   () -> market regime, totals, sentiment, breadth, movers
    scan_market                       (chain?, theme?, top_n?) -> ranked shortlist
    analyze_token                     (symbol) -> fast market + technical read
    deep_analysis                     (symbol, include_perp?) -> full evidence pack
    compare_tokens                    (symbols, intent?) -> 2-4 assets compared
    monitor_market_sentiment_shift    (time_window fixed "7d") -> 7-day sentiment shift

This module does not invent a seventh tool, does not accept a wallet address
anywhere (the guide is explicit RYO "does not accept a wallet address"), and
does not attempt to read portfolio/user state, because the guide states
plainly that RYO "cannot read user balances, positions, or portfolio state" --
that responsibility belongs to the calling application, which is why
schema.py has a separate EvidenceSource.USER_DECLARED path.
"""
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
    def from_env(cls) -> RyoClientConfig:
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

    Tool validation (which tools exist, which arguments they take) defaults
    to the module-level RYO_TOOLS/REQUIRED_ARGS table, hand-transcribed from
    the guide. Call `refresh_catalog()` once to replace that with the real,
    live `GET /tools` catalog instead -- the guide's own recommendation
    ("The catalog is authoritative. ... Read it at startup instead of
    hard-coding assumptions"). This has NOT been exercised against a live
    service in this environment (no RYO_MCP_KEY); it is implemented and
    unit-tested against a mocked transport in test_ryo_client.py, which is a
    different claim from "verified live" -- see docs/LIMITATIONS.md.
    """

    def __init__(self, config: RyoClientConfig | None = None, *, client: httpx.Client | None = None):
        self.config = config or RyoClientConfig.from_env()
        self._client = client or httpx.Client(timeout=self.config.timeout_s)
        # Defaults to the hard-coded table; refresh_catalog() replaces this
        # with the live catalog on success and leaves it untouched on
        # failure -- there is exactly one source of truth in use at any
        # moment, never two consulted at once.
        self._tool_specs: dict[str, set[str]] = dict(RYO_TOOLS)
        self._required_args: dict[str, set[str]] = dict(REQUIRED_ARGS)
        self.catalog_source = "hard-coded"  # or "live" after a successful refresh_catalog()

    def refresh_catalog(self) -> bool:
        """Fetch GET {base}/tools and, if it returns a well-formed catalog,
        make it this client's source of truth for argument validation.

        Returns True if the live catalog was adopted, False if it fell back
        to keeping the existing (hard-coded, or previous live) table --
        e.g. on a network error, non-200, or a response that doesn't parse
        as a list of {name, inputSchema} objects. Never raises for a normal
        "couldn't reach it" failure; this is meant to be safe to call
        speculatively before a run without risking that run on the catalog
        endpoint being unavailable.
        """
        try:
            catalog = self.discover_tools()
        except (httpx.TransportError, httpx.HTTPStatusError, RyoToolError, ValueError):
            return False

        if not isinstance(catalog, list):
            return False

        new_specs: dict[str, set[str]] = {}
        new_required: dict[str, set[str]] = {}
        for entry in catalog:
            if not isinstance(entry, dict) or "name" not in entry:
                return False  # malformed entry -- don't adopt a partial/broken catalog
            name = entry["name"]
            input_schema = entry.get("inputSchema") or {}
            properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
            required = input_schema.get("required", []) if isinstance(input_schema, dict) else []
            new_specs[name] = set(properties.keys())
            new_required[name] = set(required)

        if not new_specs:
            return False  # an empty catalog is more likely a bug than reality -- don't adopt it

        self._tool_specs = new_specs
        self._required_args = new_required
        self.catalog_source = "live"
        return True

    def _validate_args(self, tool: str, arguments: dict[str, Any]) -> None:
        if tool not in self._tool_specs:
            raise RyoToolError(
                f"'{tool}' is not in this client's tool catalog ({self.catalog_source}): "
                f"{sorted(self._tool_specs)}. Refusing to call an unrecognized tool."
            )
        allowed = self._tool_specs[tool]
        unknown = set(arguments) - allowed
        if unknown:
            raise RyoToolError(f"{tool} does not accept argument(s) {sorted(unknown)}")
        missing = self._required_args.get(tool, set()) - set(arguments)
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
                # Guide: "Do not retry invalid arguments or unknown tools
                # without changing the request." -- so 4xx other than 429
                # is not retried.
                body = self._safe_json(response)
                raise RyoToolError(
                    f"RYO {response.status_code} calling {tool}: {body}",
                    status_code=response.status_code,
                    trace_id=(body or {}).get("trace_id") if isinstance(body, dict) else None,
                )

            body = response.json()
            # SPEC NOTE (fixed after re-audit): the guide's own Python REST
            # client example does `response.json()["result"]`, not
            # `response.json()` directly -- the REST endpoint wraps the
            # public envelope in a top-level "result" key, the same as the
            # MCP JSON-RPC transport does. The first implementation of this
            # method read the top-level body as the envelope itself, which
            # was wrong; this was caught by re-reading the guide line by
            # line rather than trusting the earlier summary of it.
            if not isinstance(body, dict) or "result" not in body:
                raise RyoToolError(
                    f"unexpected REST response shape for {tool}: expected a "
                    "top-level 'result' key per MCP-Builder-Guide.md's own "
                    f"Python REST example, got keys={list(body) if isinstance(body, dict) else type(body).__name__}"
                )
            return parse_envelope(body["result"])

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
        except ValueError:
            # response.json() raises json.JSONDecodeError (a ValueError
            # subclass) on non-JSON bodies -- narrowed from a blind except
            # so a genuine bug elsewhere in this method isn't silently
            # swallowed along with the case this is actually for.
            return {"raw_text": response.text}

    def health(self) -> dict[str, Any]:
        """GET {base}/health -- guide: "Health does not require authentication."
        Implemented per spec; not exercised against the live service here.
        """
        response = self._client.get(f"{self.config.base_url}/health")
        response.raise_for_status()
        return response.json()

    def whoami(self) -> dict[str, Any]:
        """GET {base}/whoami -- guide: "Reading `whoami` does not consume
        tool-call quota." Implemented per spec; not exercised live here.
        """
        response = self._client.get(
            f"{self.config.base_url}/whoami",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
        )
        response.raise_for_status()
        return response.json()

    def discover_tools(self) -> dict[str, Any]:
        """GET {base}/tools -- guide: "The catalog is authoritative. ...
        Read it at startup instead of hard-coding assumptions."

        Returns the raw list of {name, description, inputSchema} objects
        (matching RYO's real McpToolInfo schema, confirmed against
        docs/ryo-openapi-subset.json's paths['/api/mcp/tools']). Call
        refresh_catalog() instead of this directly if the goal is to update
        this client's own argument-validation table -- that method wraps
        this one with the "don't adopt a broken catalog" safety checks.
        """
        response = self._client.get(
            f"{self.config.base_url}/tools",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()


class FixtureRyoClient:
    """Replays a hand-built fixture envelope instead of calling RYO.

    Used only for local development and the parts of the test suite that
    exercise the resolver/evaluator against a realistic envelope shape
    without a live RYO_MCP_KEY. Every fixture file is labelled
    `"source": "fixture"` inside itself (see tests/fixtures/envelopes/) so
    nothing produced this way can be mistaken for a live RYO read -- the
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
