from strategy_compiler.evaluator import evaluate_rule, evaluate_strategy
from strategy_compiler.schema import (
    ComparisonOperator,
    EvidenceRequirement,
    EvidenceSource,
    ResolvedEvidence,
    Rule,
    RuleResultStatus,
    RuleStatus,
    Strategy,
)


def _rule(**kwargs) -> Rule:
    defaults = dict(
        id="rule_1",
        raw_text="test",
        status=RuleStatus.EXECUTABLE,
        asset="SOL",
        metric="momentum_state",
        operator=ComparisonOperator.EQ,
        value="positive",
    )
    defaults.update(kwargs)
    return Rule(**defaults)


def _evidence(rule: Rule, value, available=True) -> ResolvedEvidence:
    req = EvidenceRequirement(metric=rule.metric, source=EvidenceSource.RYO_TOOL, ryo_tool="analyze_token")
    return ResolvedEvidence(rule_id=rule.id, requirement=req, available=available, value=value)


def test_pass_when_condition_met():
    rule = _rule(operator=ComparisonOperator.GT, value=50)
    ev = _evidence(rule, 62.4)  
    result = evaluate_rule(rule, ev)
    assert result.status is RuleResultStatus.PASS


def test_fail_when_condition_not_met():
    rule = _rule(operator=ComparisonOperator.GT, value=70)
    ev = _evidence(rule, 62.4)
    result = evaluate_rule(rule, ev)
    assert result.status is RuleResultStatus.FAIL


def test_unknown_when_evidence_unavailable():
    rule = _rule()
    ev = _evidence(rule, None, available=False)
    result = evaluate_rule(rule, ev)
    assert result.status is RuleResultStatus.UNKNOWN


def test_skipped_for_non_executable_rule():
    rule = _rule(status=RuleStatus.NEEDS_CLARIFICATION, operator=None, value=None, problem="vague")
    result = evaluate_rule(rule, None)
    assert result.status is RuleResultStatus.SKIPPED


def test_momentum_symbolic_threshold_positive():
    rule = _rule(operator=ComparisonOperator.EQ, value="positive")
    ev = _evidence(rule, 62.4)  # RSI above 55 threshold -> "positive"
    result = evaluate_rule(rule, ev)
    assert result.status is RuleResultStatus.PASS


def test_momentum_symbolic_threshold_negative_fails_positive_check():
    rule = _rule(operator=ComparisonOperator.EQ, value="positive")
    ev = _evidence(rule, 30.0)  # RSI below 45 -> "negative"
    result = evaluate_rule(rule, ev)
    assert result.status is RuleResultStatus.FAIL


def test_decision_allow_when_all_pass():
    rule = _rule(operator=ComparisonOperator.GT, value=50)
    ev = _evidence(rule, 62.4)
    strategy = Strategy(raw_text="x", rules=(rule,), compiler_model="fixture:test", compiled_at="now")
    decision, results = evaluate_strategy(strategy, {rule.id: ev})
    assert decision == "ALLOW"


def test_decision_block_when_any_fail():
    rule = _rule(operator=ComparisonOperator.GT, value=90)
    ev = _evidence(rule, 62.4)
    strategy = Strategy(raw_text="x", rules=(rule,), compiler_model="fixture:test", compiled_at="now")
    decision, results = evaluate_strategy(strategy, {rule.id: ev})
    assert decision == "BLOCK"
    assert results[0].status is RuleResultStatus.FAIL


def test_decision_unknown_when_evidence_missing_and_nothing_fails():
    rule = _rule()
    ev = _evidence(rule, None, available=False)
    strategy = Strategy(raw_text="x", rules=(rule,), compiler_model="fixture:test", compiled_at="now")
    decision, results = evaluate_strategy(strategy, {rule.id: ev})
    assert decision == "UNKNOWN"


def test_fail_beats_unknown_in_same_strategy():
    failing = _rule(id="rule_1", operator=ComparisonOperator.GT, value=90)
    failing_ev = _evidence(failing, 62.4)
    unknown = _rule(id="rule_2", metric="market_regime", operator=ComparisonOperator.EQ, value="risk_on")
    unknown_ev = _evidence(unknown, None, available=False)
    strategy = Strategy(
        raw_text="x", rules=(failing, unknown), compiler_model="fixture:test", compiled_at="now"
    )
    decision, results = evaluate_strategy(strategy, {failing.id: failing_ev, unknown.id: unknown_ev})
    assert decision == "BLOCK"
