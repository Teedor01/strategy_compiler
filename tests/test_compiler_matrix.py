from strategy_compiler.compiler import compile_strategy
from strategy_compiler.decide import decide
from strategy_compiler.fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from strategy_compiler.ryo_client import FixtureRyoClient
from strategy_compiler.schema import RuleStatus

ALLOW_STRATEGY = (
    "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 20% of the portfolio."
)
BLOCK_STRATEGY = (
    "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 10% of the portfolio."
)
MULTI_BLOCK_STRATEGY = "Buy SOL only if momentum is above 90 and SOL stays below 5% of the portfolio."


def _ryo():
    return FixtureRyoClient(load_envelope_fixtures())


def test_fully_executable_strategy_allows():
    receipt = decide(ALLOW_STRATEGY, llm=DEMO_FIXTURE_LLM, ryo=_ryo(), user_declared={"allocation_pct": 0.15})
    assert receipt.decision == "ALLOW"
    assert receipt.blocking_rule_ids == ()
    assert receipt.unresolved_rule_ids == ()


def test_executable_strategy_with_failed_constraint_blocks():
    receipt = decide(BLOCK_STRATEGY, llm=DEMO_FIXTURE_LLM, ryo=_ryo(), user_declared={"allocation_pct": 0.15})
    assert receipt.decision == "BLOCK"
    assert receipt.blocking_rule_ids == ("rule_3",)


def test_undefined_threshold_needs_clarification():
    strategy = compile_strategy("Buy SOL only when momentum is strong.", DEMO_FIXTURE_LLM)
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION


def test_unsupported_evidence_is_unsupported_and_decision_is_unknown():
    receipt = decide(
        "Never trade if the required safety check fails.", llm=DEMO_FIXTURE_LLM, ryo=_ryo(), user_declared={}
    )
    assert receipt.strategy.rules[0].status is RuleStatus.UNSUPPORTED
    assert receipt.decision == "UNKNOWN"
    assert receipt.unresolved_rule_ids == ("rule_1",)


def test_contradictory_rules_are_conflicting_and_decision_is_unknown():
    receipt = decide(
        "Buy SOL when momentum is above 60 and SOL momentum is below 40.",
        llm=DEMO_FIXTURE_LLM,
        ryo=_ryo(),
        user_declared={},
    )
    assert all(r.status is RuleStatus.CONFLICTING for r in receipt.strategy.rules)
    assert receipt.decision == "UNKNOWN"
    assert set(receipt.unresolved_rule_ids) == {"rule_1", "rule_2"}


def test_multiple_blocking_rules_are_all_named():
    receipt = decide(
        MULTI_BLOCK_STRATEGY, llm=DEMO_FIXTURE_LLM, ryo=_ryo(), user_declared={"allocation_pct": 0.15}
    )
    assert receipt.decision == "BLOCK"
    assert set(receipt.blocking_rule_ids) == {"rule_1", "rule_2"}


def test_multiple_assets_each_resolved_independently():
    receipt = decide(ALLOW_STRATEGY, llm=DEMO_FIXTURE_LLM, ryo=_ryo(), user_declared={"allocation_pct": 0.15})
    assets = {rule.asset for rule in receipt.strategy.rules}
    assert assets == {"SOL", "BTC"}
    sources_by_asset = {
        rule.asset: next(r.evidence for r in receipt.rule_results if r.rule_id == rule.id).requirement.ryo_tool
        for rule in receipt.strategy.rules
        if rule.metric != "allocation_pct"
    }
    assert sources_by_asset == {"SOL": "analyze_token", "BTC": "market_overview"}


def test_allocation_constraint_resolves_from_user_declared_not_ryo():
    receipt = decide(ALLOW_STRATEGY, llm=DEMO_FIXTURE_LLM, ryo=_ryo(), user_declared={"allocation_pct": 0.15})
    allocation_result = next(r for r in receipt.rule_results if r.explanation.startswith("allocation_pct"))
    assert allocation_result.evidence.requirement.source.value == "user_declared"


def test_original_human_wording_is_preserved_verbatim():
    strategy = compile_strategy(ALLOW_STRATEGY, DEMO_FIXTURE_LLM)
    raw_clauses = {rule.raw_text for rule in strategy.rules}
    assert raw_clauses == {
        "momentum is positive",
        "BTC isn't bearish",
        "SOL stays below 20% of the portfolio",
    }
    for clause in raw_clauses:
        assert clause in strategy.raw_text


def test_compilation_of_identical_input_is_deterministic():
    strategy_a = compile_strategy(ALLOW_STRATEGY, DEMO_FIXTURE_LLM)
    strategy_b = compile_strategy(ALLOW_STRATEGY, DEMO_FIXTURE_LLM)

    def _stable(strategy):
        return [
            (r.id, r.status.value, r.asset, r.metric, r.operator, r.value, r.raw_text)
            for r in strategy.rules
        ]

    assert _stable(strategy_a) == _stable(strategy_b)
    assert strategy_a.compiler_model == strategy_b.compiler_model
    assert strategy_a.raw_text == strategy_b.raw_text
