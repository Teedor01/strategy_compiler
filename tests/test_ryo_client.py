from __future__ import annotations

import httpx
import pytest

from strategy_compiler.ryo_client import (
    RYO_TOOLS,
    RyoClient,
    RyoClientConfig,
    RyoToolError,
)

CONFIG = RyoClientConfig(base_url="https://app-ryochan.com/api/mcp", api_key="test-key", max_retries=3)

WRAPPED_ENVELOPE = {
    "result": {
        "schema_version": "1.0",
        "tool": "analyze_token",
        "status": "ok",
        "data_mode": "live",
        "as_of": "2026-09-26T00:00:00Z",
        "request": {"symbol": "SOL"},
        "data": {"technicals": {"rsi_14": 58.2}},
        "summary": {"headline": "SOL RSI 58.2", "key_points": []},
        "availability": {"technicals": "available"},
        "warnings": [],
    }
}


def _client_with_transport(transport: httpx.MockTransport) -> RyoClient:
    return RyoClient(config=CONFIG, client=httpx.Client(transport=transport))


def test_call_unwraps_the_result_key_per_the_guides_own_example():
    """The exact bug found during re-audit: the guide's Python REST example
    does response.json()["result"], not response.json() directly.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/tools/analyze_token/call")
        return httpx.Response(200, json=WRAPPED_ENVELOPE)

    client = _client_with_transport(httpx.MockTransport(handler))
    envelope = client.call("analyze_token", {"symbol": "SOL"})
    assert envelope.tool == "analyze_token"
    assert envelope.data["technicals"]["rsi_14"] == 58.2


def test_call_raises_clearly_on_unexpected_shape_rather_than_guessing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"schema_version": "1.0", "tool": "analyze_token"})  # no "result" key

    client = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(RyoToolError, match="expected a top-level 'result' key"):
        client.call("analyze_token", {"symbol": "SOL"})


def test_429_is_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "rate limited"})
        return httpx.Response(200, json=WRAPPED_ENVELOPE)

    client = _client_with_transport(httpx.MockTransport(handler))
    envelope = client.call("analyze_token", {"symbol": "SOL"})
    assert calls["n"] == 2
    assert envelope.status == "ok"


def test_400_is_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"code": "invalid_argument", "message": "bad symbol", "trace_id": "abc123"})

    client = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(RyoToolError) as exc_info:
        client.call("analyze_token", {"symbol": "SOL"})
    assert calls["n"] == 1  
    assert exc_info.value.status_code == 400
    assert exc_info.value.trace_id == "abc123"


def test_unknown_tool_name_is_rejected_before_any_http_call():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=WRAPPED_ENVELOPE)

    client = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(RyoToolError, match="not in this client's tool catalog"):
        client.call("check_safety", {})  # real RYO SkillName, but NOT one of the six Builder MCP tools
    assert calls["n"] == 0


def test_missing_required_argument_is_rejected_before_any_http_call():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=WRAPPED_ENVELOPE)

    client = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(RyoToolError, match="requires argument"):
        client.call("analyze_token", {})  # symbol is required



LIVE_CATALOG = [
    {
        "name": "analyze_token",
        "description": "...",
        "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
    },
    {
        "name": "market_overview",
        "description": "...",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_liquidity_depth",
        "description": "...",
        "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
    },
]


def test_refresh_catalog_adopts_live_tool_list_as_source_of_truth():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/tools")
        return httpx.Response(200, json=LIVE_CATALOG)

    client = _client_with_transport(httpx.MockTransport(handler))
    assert client.catalog_source == "hard-coded"
    ok = client.refresh_catalog()
    assert ok is True
    assert client.catalog_source == "live"
    assert "check_liquidity_depth" in client._tool_specs
    assert "check_liquidity_depth" not in RYO_TOOLS


def test_refresh_catalog_derives_required_args_from_live_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=LIVE_CATALOG)

    client = _client_with_transport(httpx.MockTransport(handler))
    client.refresh_catalog()
    with pytest.raises(RyoToolError, match="requires argument"):
        client._validate_args("check_liquidity_depth", {}) 


def test_refresh_catalog_fails_closed_on_network_error_keeps_fallback():
    def handler(request: httpx.Request) -> httpx.Request:
        raise httpx.ConnectError("simulated network failure", request=request)

    client = _client_with_transport(httpx.MockTransport(handler))
    ok = client.refresh_catalog()
    assert ok is False
    assert client.catalog_source == "hard-coded"
    assert client._tool_specs == RYO_TOOLS  


def test_refresh_catalog_fails_closed_on_malformed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "a list"})

    client = _client_with_transport(httpx.MockTransport(handler))
    ok = client.refresh_catalog()
    assert ok is False
    assert client.catalog_source == "hard-coded"


def test_refresh_catalog_fails_closed_on_empty_catalog():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _client_with_transport(httpx.MockTransport(handler))
    ok = client.refresh_catalog()
    assert ok is False  
    assert client.catalog_source == "hard-coded"


def test_call_uses_live_catalog_after_successful_refresh():
    """End-to-end: refresh, then call() itself validates against the live
    table, not the module-level fallback.
    """
    call_log = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append(request.url.path)
        if request.url.path.endswith("/tools"):
            return httpx.Response(200, json=LIVE_CATALOG)
        return httpx.Response(200, json=WRAPPED_ENVELOPE)

    client = _client_with_transport(httpx.MockTransport(handler))
    client.refresh_catalog()
    envelope = client.call("check_liquidity_depth", {"symbol": "SOL"})  
    assert envelope.status == "ok"
