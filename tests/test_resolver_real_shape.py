from strategy_compiler import resolver
from strategy_compiler.envelope import parse_envelope
from strategy_compiler.ryo_client import FixtureRyoClient
from strategy_compiler.schema import ComparisonOperator, Rule, RuleStatus

REAL_SHAPE_ANALYZE_TOKEN = {
    "schema_version": "1.0",
    "tool": "analyze_token",
    "status": "ok",
    "data_mode": "simulated",
    "as_of": "2026-09-20T00:00:00Z",
    "request": {"symbol": "SOL"},
    "data": {
        "asset": {"symbol": "SOL", "name": "Solana", "chain": None, "contract": None, "rank": 7},
        "market": {"price_usd": 111.0, "market_cap_usd": 1.0, "fully_diluted_value_usd": 1.0, "volume_24h_usd": 1.0},
        "performance": {"change_1h_pct": 0.0, "change_24h_pct": 0.0, "change_7d_pct": 0.0, "change_30d_pct": 0.0},
        "technical_analysis": {"trend": "up", "rsi_14": 66.9, "momentum_30d_pct": 28.6, "atr_14_pct": 4.3},
        "intelligence": {"narrative": "placeholder", "catalysts": [], "risks": []},
        "verdict": "accumulate",
    },
    "summary": {"headline": "[FIXTURE, real-shaped] SOL", "key_points": []},
    "availability": {"technical_analysis": "available"},
    "warnings": ["hand-built fixture with the real field structure, not a live response"],
}


def test_momentum_state_resolves_against_real_field_structure():
    client = FixtureRyoClient({"analyze_token": parse_envelope(REAL_SHAPE_ANALYZE_TOKEN)})
    rule = Rule(
        id="rule_1",
        raw_text="test",
        status=RuleStatus.EXECUTABLE,
        asset="SOL",
        metric="momentum_state",
        operator=ComparisonOperator.GT,
        value=50,
    )
    ev = resolver.resolve(rule, client.call)
    assert ev.available is True
    assert ev.value == 66.9 
