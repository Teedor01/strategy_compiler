from strategy_compiler.decide import decide
from strategy_compiler.fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from strategy_compiler.ryo_client import FixtureRyoClient


def test_same_evidence_different_rule_different_decision():
    ryo = FixtureRyoClient(load_envelope_fixtures())  # identical evidence both runs

    receipt_20pct = decide(
        "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 20% of the portfolio.",
        llm=DEMO_FIXTURE_LLM,
        ryo=ryo,
        user_declared={"allocation_pct": 0.15},  
    )
    assert receipt_20pct.decision == "ALLOW"  

    receipt_10pct = decide(
        "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 10% of the portfolio.",
        llm=DEMO_FIXTURE_LLM,
        ryo=ryo,
        user_declared={"allocation_pct": 0.15},  
    )
    assert receipt_10pct.decision == "BLOCK"  # 0.15 < 0.10 is false -> the same evidence now fails


    blocking_rules = [r for r in receipt_10pct.strategy.rules if r.id in receipt_10pct.blocking_rule_ids]
    assert len(blocking_rules) == 1
    assert blocking_rules[0].metric == "allocation_pct"


    momentum_result_20 = next(r for r in receipt_20pct.rule_results if r.explanation.startswith("momentum_state"))
    momentum_result_10 = next(r for r in receipt_10pct.rule_results if r.explanation.startswith("momentum_state"))
    assert momentum_result_20.status.value == momentum_result_10.status.value == "PASS"


    assert receipt_20pct.trace_id != receipt_10pct.trace_id
