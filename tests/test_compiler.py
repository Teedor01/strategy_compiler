from strategy_compiler.compiler import compile_strategy
from strategy_compiler.fixtures import DEMO_FIXTURE_LLM
from strategy_compiler.schema import RuleStatus


def test_vague_momentum_needs_clarification():
    strategy = compile_strategy("Buy SOL only when momentum is strong.", DEMO_FIXTURE_LLM)
    assert len(strategy.rules) == 1
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
    assert "strong" in strategy.rules[0].problem


def test_looking_bad_needs_clarification_not_invented():
    strategy = compile_strategy("If BTC is looking bad, just leave the alt alone.", DEMO_FIXTURE_LLM)
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
    # must not have silently invented a market_regime value
    assert strategy.rules[0].value is None


def test_too_much_of_the_pot_needs_clarification():
    strategy = compile_strategy("Don't put too much of the pot into one coin.", DEMO_FIXTURE_LLM)
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
    assert strategy.rules[0].value is None


def test_safety_check_is_unsupported_no_ryo_safety_tool():
    strategy = compile_strategy("Never trade if the required safety check fails.", DEMO_FIXTURE_LLM)
    assert strategy.rules[0].status is RuleStatus.UNSUPPORTED
    assert "safety_check" in (strategy.rules[0].metric or "")


def test_contradictory_rules_are_flagged_conflicting():
    strategy = compile_strategy(
        "Buy SOL when momentum is above 60 and SOL momentum is below 40.", DEMO_FIXTURE_LLM
    )
    assert len(strategy.rules) == 2
    assert all(r.status is RuleStatus.CONFLICTING for r in strategy.rules)
    assert strategy.rules[0].id in strategy.rules[1].conflicts_with
    assert strategy.rules[1].id in strategy.rules[0].conflicts_with


def test_unsupported_evidence_wallet_cluster_risk():
    strategy = compile_strategy(
        "Only buy SOL if it requires evidence RYO cannot provide, like wallet cluster risk.",
        DEMO_FIXTURE_LLM,
    )
    assert strategy.rules[0].status is RuleStatus.UNSUPPORTED


def test_fully_specified_rule_is_executable():
    strategy = compile_strategy("Buy SOL when SOL momentum is above 50.", DEMO_FIXTURE_LLM)
    assert strategy.rules[0].status is RuleStatus.EXECUTABLE
    assert strategy.rules[0].asset == "SOL"
    assert strategy.rules[0].metric == "momentum_state"


def test_fixture_llm_refuses_unknown_input():
    import pytest

    with pytest.raises(KeyError):
        compile_strategy("something never registered as a fixture", DEMO_FIXTURE_LLM)
