from strategy_compiler.decide import decide
from strategy_compiler.fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from strategy_compiler.ryo_client import FixtureRyoClient

SCENARIO_A = "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 20% of the portfolio."
SCENARIO_B = "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 10% of the portfolio."
PROPOSED_ALLOCATION = 0.15  


def test_changing_only_the_policy_threshold_flips_the_decision():
    ryo_a = FixtureRyoClient(load_envelope_fixtures())
    ryo_b = FixtureRyoClient(load_envelope_fixtures())

    receipt_a = decide(SCENARIO_A, llm=DEMO_FIXTURE_LLM, ryo=ryo_a, user_declared={"allocation_pct": PROPOSED_ALLOCATION})
    receipt_b = decide(SCENARIO_B, llm=DEMO_FIXTURE_LLM, ryo=ryo_b, user_declared={"allocation_pct": PROPOSED_ALLOCATION})

    # --- assert the evidence really was identical, not just "probably" ---
    momentum_a = next(r.evidence for r in receipt_a.rule_results if r.evidence and r.evidence.requirement.metric == "momentum_state")
    momentum_b = next(r.evidence for r in receipt_b.rule_results if r.evidence and r.evidence.requirement.metric == "momentum_state")
    assert momentum_a.value == momentum_b.value  # identical RYO evidence, both runs

    regime_a = next(r.evidence for r in receipt_a.rule_results if r.evidence and r.evidence.requirement.metric == "market_regime")
    regime_b = next(r.evidence for r in receipt_b.rule_results if r.evidence and r.evidence.requirement.metric == "market_regime")
    assert regime_a.value == regime_b.value  # identical RYO evidence, both runs

    allocation_a = next(r.evidence for r in receipt_a.rule_results if r.evidence and r.evidence.requirement.metric == "allocation_pct")
    allocation_b = next(r.evidence for r in receipt_b.rule_results if r.evidence and r.evidence.requirement.metric == "allocation_pct")
    assert allocation_a.value == allocation_b.value == PROPOSED_ALLOCATION  # identical declared position, both runs

    # --- assert the two rule SETS differ in exactly the one place the human wording differs ---
    threshold_a = next(r.value for r in receipt_a.strategy.rules if r.metric == "allocation_pct")
    threshold_b = next(r.value for r in receipt_b.strategy.rules if r.metric == "allocation_pct")
    assert threshold_a == 0.20
    assert threshold_b == 0.10
    non_allocation_rules_a = [(r.metric, r.operator, r.value) for r in receipt_a.strategy.rules if r.metric != "allocation_pct"]
    non_allocation_rules_b = [(r.metric, r.operator, r.value) for r in receipt_b.strategy.rules if r.metric != "allocation_pct"]
    assert non_allocation_rules_a == non_allocation_rules_b  # every OTHER rule is identical

    # --- assert the decisions actually differ, and WHY, at rule level ---
    assert receipt_a.decision == "ALLOW"
    assert receipt_b.decision == "BLOCK"
    assert receipt_a.blocking_rule_ids == ()
    assert len(receipt_b.blocking_rule_ids) == 1

    blocking_rule_b = next(r for r in receipt_b.strategy.rules if r.id in receipt_b.blocking_rule_ids)
    assert blocking_rule_b.metric == "allocation_pct"  # the SAME metric whose threshold changed, not a side effect
    assert blocking_rule_b.value == 0.10

    blocking_result_b = next(r for r in receipt_b.rule_results if r.rule_id == blocking_rule_b.id)
    assert blocking_result_b.status.value == "FAIL"
    assert "0.15" in blocking_result_b.explanation or "0.1" in str(blocking_result_b.explanation)

    # --- the two OTHER rules (momentum, regime) must both still PASS in scenario B ---
    other_results_b = [r for r in receipt_b.rule_results if r.rule_id != blocking_rule_b.id]
    assert all(r.status.value == "PASS" for r in other_results_b)

    # --- and the receipts themselves must be distinguishable artifacts ---
    assert receipt_a.trace_id != receipt_b.trace_id
