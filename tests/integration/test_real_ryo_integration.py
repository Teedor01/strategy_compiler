import os

import pytest

from strategy_compiler.ryo_client import RyoClient, RyoClientConfig, RyoConfigError

RYO_MCP_URL = os.environ.get("RYO_MCP_URL", "")
RYO_MCP_KEY = os.environ.get("RYO_MCP_KEY", "")
_HAS_CREDENTIALS = bool(RYO_MCP_URL and RYO_MCP_KEY)


@pytest.mark.skipif(
    not _HAS_CREDENTIALS,
    reason="SKIPPED: RYO_MCP_KEY not configured (set RYO_MCP_URL and RYO_MCP_KEY to run this for real)",
)
def test_market_overview_against_the_live_ryo_service():
    """Only runs when RYO_MCP_URL and RYO_MCP_KEY are both set. Calls
    market_overview specifically because the guide states it takes no
    arguments and "is never a prerequisite for another call" -- the
    cheapest possible real call to prove the whole chain (auth, transport,
    envelope unwrapping, envelope parsing) actually works end to end.

    The credential value itself is never asserted on, printed, or included
    in any failure message below -- only its presence/absence.
    """
    client = RyoClient(RyoClientConfig.from_env())
    try:
        catalog_ok = client.refresh_catalog()
        assert catalog_ok is True, (
            "RYO_MCP_KEY is configured but refresh_catalog() could not adopt "
            "the live /tools catalog -- either the endpoint or its schema "
            "has changed from what docs/ryo-openapi-subset.json documents."
        )
        assert client.catalog_source == "live"
        envelope = client.call("market_overview", {})
    finally:
        client.close()

    assert envelope.tool == "market_overview"
    assert envelope.status in {"ok", "partial", "unavailable"}
    assert envelope.data_mode in {"live", "mixed", "simulated", "unknown"}
    assert envelope.data_mode != "simulated", (
        "RYO_MCP_KEY is configured but the response reports data_mode="
        "'simulated' -- verify this is actually pointed at a live "
        "environment, not a sandbox/test credential."
    )


def test_config_from_env_raises_a_clear_error_without_credentials(monkeypatch):
    """This one always runs, regardless of credentials... it's checking the
    error path itself, not the live service, so it needs the *absence* of
    config to exercise correctly.
    """
    monkeypatch.delenv("RYO_MCP_URL", raising=False)
    monkeypatch.delenv("RYO_MCP_KEY", raising=False)
    with pytest.raises(RyoConfigError):
        RyoClientConfig.from_env()
