from strategy_compiler.evaluator import evaluate_strategy
from strategy_compiler.receipt import build_receipt
from strategy_compiler.schema import (
    ComparisonOperator,
    EvidenceRequirement,
    EvidenceSource,
    ResolvedEvidence,
    Rule,
    RuleStatus,
    Strategy,
)


def _strategy_and_evidence(value: float):
    rule = Rule(
        id="rule_1",
        raw_text="momentum above 50",
        status=RuleStatus.EXECUTABLE,
        asset="SOL",
        metric="momentum_state",
        operator=ComparisonOperator.GT,
        value=50,
    )
    strategy = Strategy(raw_text="x", rules=(rule,), compiler_model="fixture:test", compiled_at="now")
    req = EvidenceRequirement(metric="momentum_state", source=EvidenceSource.RYO_TOOL, ryo_tool="analyze_token")
    ev = ResolvedEvidence(rule_id="rule_1", requirement=req, available=True, value=value)
    return strategy, {"rule_1": ev}


def test_same_inputs_produce_same_trace_id():
    strategy, evidence = _strategy_and_evidence(62.4)
    decision1, results1 = evaluate_strategy(strategy, evidence)
    receipt1 = build_receipt(strategy, decision1, results1)

    decision2, results2 = evaluate_strategy(strategy, evidence)
    receipt2 = build_receipt(strategy, decision2, results2)

    assert receipt1.trace_id == receipt2.trace_id
    assert receipt1.decision == receipt2.decision == "ALLOW"


def test_different_evidence_changes_trace_id_and_decision():
    strategy_a, evidence_a = _strategy_and_evidence(62.4)  # passes GT 50
    strategy_b, evidence_b = _strategy_and_evidence(30.0)  # fails GT 50

    decision_a, results_a = evaluate_strategy(strategy_a, evidence_a)
    receipt_a = build_receipt(strategy_a, decision_a, results_a)

    decision_b, results_b = evaluate_strategy(strategy_b, evidence_b)
    receipt_b = build_receipt(strategy_b, decision_b, results_b)

    assert receipt_a.trace_id != receipt_b.trace_id
    assert receipt_a.decision == "ALLOW"
    assert receipt_b.decision == "BLOCK"
    assert receipt_b.blocking_rule_ids == ("rule_1",)
