from strategy_compiler import resolver
from strategy_compiler.compiler import compile_strategy
from strategy_compiler.decide import decide
from strategy_compiler.fixtures import load_envelope_fixtures
from strategy_compiler.ryo_client import FixtureRyoClient
from strategy_compiler.schema import ComparisonOperator, Rule, RuleStatus


def _rule(metric, operator, value, asset="SOL") -> Rule:
    return Rule(
        id="rule_1",
        raw_text="test",
        status=RuleStatus.EXECUTABLE,
        asset=asset,
        metric=metric,
        operator=operator,
        value=value,
    )


def test_price_usd_resolves_from_analyze_token():
    client = FixtureRyoClient(load_envelope_fixtures())
    rule = _rule("price_usd", ComparisonOperator.LT, 200)
    ev = resolver.resolve(rule, client.call)
    assert ev.available is True
    assert ev.value == 111.76


def test_change_24h_pct_resolves_from_analyze_token():
    client = FixtureRyoClient(load_envelope_fixtures())
    rule = _rule("change_24h_pct", ComparisonOperator.LT, 10)
    ev = resolver.resolve(rule, client.call)
    assert ev.available is True
    assert ev.value == 1.32


def test_market_cap_rank_resolves_from_analyze_token():
    client = FixtureRyoClient(load_envelope_fixtures())
    rule = _rule("market_cap_rank", ComparisonOperator.LTE, 10)
    ev = resolver.resolve(rule, client.call)
    assert ev.available is True
    assert ev.value == 7


def test_fear_greed_index_resolves_from_market_overview():
    client = FixtureRyoClient(load_envelope_fixtures())
    rule = _rule("fear_greed_index", ComparisonOperator.GT, 50, asset=None)
    ev = resolver.resolve(rule, client.call)
    assert ev.available is True
    assert ev.value == 74.0


def test_price_and_momentum_share_one_analyze_token_call_conceptually():
    """Both metrics resolve from the same tool -- confirms the registry
    entry doesn't accidentally point at a second, unnecessary RYO call.
    """
    assert resolver.REGISTRY["price_usd"].ryo_tool == "analyze_token"
    assert resolver.REGISTRY["momentum_state"].ryo_tool == "analyze_token"
    assert resolver.REGISTRY["fear_greed_index"].ryo_tool == "market_overview"
    assert resolver.REGISTRY["market_regime"].ryo_tool == "market_overview"



CANNED = {
    "Buy SOL only if the price is below $200.": [
        {"raw_text": "the price is below $200", "asset": "SOL", "metric": "price_usd", "operator": "<", "value": 200, "ambiguity_note": None}
    ],
    "Don't buy SOL if it's up more than 10% in the last 24 hours.": [
        {"raw_text": "up more than 10% in the last 24 hours", "asset": "SOL", "metric": "change_24h_pct", "operator": "<=", "value": 10, "ambiguity_note": None}
    ],
    "Only buy tokens ranked in the top 10 by market cap.": [
        {"raw_text": "ranked in the top 10 by market cap", "asset": "SOL", "metric": "market_cap_rank", "operator": "<=", "value": 10, "ambiguity_note": None}
    ],
    "Buy SOL only when the Fear and Greed index is above 60.": [
        {"raw_text": "Fear and Greed index is above 60", "asset": None, "metric": "fear_greed_index", "operator": ">", "value": 60, "ambiguity_note": None}
    ],
}


def _llm_with(extra):
    from strategy_compiler.llm import FixtureLLM

    return FixtureLLM(extra)


def test_price_threshold_end_to_end_allow():
    receipt = decide(
        "Buy SOL only if the price is below $200.",
        llm=_llm_with(CANNED),
        ryo=FixtureRyoClient(load_envelope_fixtures()),
        user_declared={},
    )
    assert receipt.decision == "ALLOW"  # 111.76 < 200


def test_change_24h_threshold_end_to_end_allow():
    receipt = decide(
        "Don't buy SOL if it's up more than 10% in the last 24 hours.",
        llm=_llm_with(CANNED),
        ryo=FixtureRyoClient(load_envelope_fixtures()),
        user_declared={},
    )
    assert receipt.decision == "ALLOW"  


def test_market_cap_rank_threshold_end_to_end_allow():
    receipt = decide(
        "Only buy tokens ranked in the top 10 by market cap.",
        llm=_llm_with(CANNED),
        ryo=FixtureRyoClient(load_envelope_fixtures()),
        user_declared={},
    )
    assert receipt.decision == "ALLOW"  


def test_fear_greed_threshold_end_to_end_allow():
    receipt = decide(
        "Buy SOL only when the Fear and Greed index is above 60.",
        llm=_llm_with(CANNED),
        ryo=FixtureRyoClient(load_envelope_fixtures()),
        user_declared={},
    )
    assert receipt.decision == "ALLOW"  # 74.0 > 60


def test_new_metric_with_vague_language_still_needs_clarification():
    """Adding new metrics must not relax the existing anti-hallucination
    rule: a vague statement about a NEW metric still refuses to invent a
    threshold, same as the original three metrics.
    """
    vague_pump = {
        "Don't chase SOL after a huge pump.": [
            {
                "raw_text": "after a huge pump",
                "asset": "SOL",
                "metric": "change_24h_pct",
                "operator": None,
                "value": None,
                "ambiguity_note": "'huge pump' has no defined percentage threshold",
            }
        ]
    }
    strategy = compile_strategy("Don't chase SOL after a huge pump.", _llm_with(vague_pump))
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
