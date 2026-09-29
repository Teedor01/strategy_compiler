from strategy_compiler import resolver
from strategy_compiler.fixtures import load_envelope_fixtures
from strategy_compiler.ryo_client import FixtureRyoClient
from strategy_compiler.schema import ComparisonOperator, Rule, RuleStatus


def _rule(metric, asset="SOL") -> Rule:
    return Rule(
        id="rule_1",
        raw_text="test",
        status=RuleStatus.EXECUTABLE,
        asset=asset,
        metric=metric,
        operator=ComparisonOperator.GT,
        value=50,
    )


def test_ryo_backed_metric_resolves_from_fixture():
    client = FixtureRyoClient(load_envelope_fixtures())
    rule = _rule("momentum_state")
    ev = resolver.resolve(rule, client.call)
    assert ev.available is True
    assert ev.value == 62.4
    assert ev.data_mode == "simulated"


def test_user_declared_metric_requires_caller_input():
    client = FixtureRyoClient(load_envelope_fixtures())
    rule = _rule("allocation_pct")
    ev_missing = resolver.resolve(rule, client.call)
    assert ev_missing.available is False

    ev_present = resolver.resolve(rule, client.call, user_declared={"allocation_pct": 0.15})
    assert ev_present.available is True
    assert ev_present.value == 0.15


def test_ryo_tool_not_in_fixture_is_unavailable_not_crashing():
    client = FixtureRyoClient(load_envelope_fixtures())  # no compare_tokens/deep_analysis loaded
    rule = _rule("market_regime")  # this one IS loaded (market_overview)
    ev = resolver.resolve(rule, client.call)
    assert ev.available is True
    assert ev.value == "risk_on"


def test_unknown_metric_raises_programmer_error_not_silent_guess():
    import pytest

    client = FixtureRyoClient(load_envelope_fixtures())
    rule = _rule("totally_invented_metric")
    with pytest.raises(KeyError):
        resolver.resolve(rule, client.call)
