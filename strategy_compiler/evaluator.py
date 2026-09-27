from __future__ import annotations

from typing import Callable

from .schema import (
    ComparisonOperator,
    Decision,
    ResolvedEvidence,
    Rule,
    RuleResult,
    RuleResultStatus,
    RuleStatus,
    Strategy,
)

EVALUATOR_VERSION = "strategy-compiler-evaluator/0.1.0"

_OPS: dict[ComparisonOperator, Callable[[object, object], bool]] = {
    ComparisonOperator.GT: lambda a, b: a > b,
    ComparisonOperator.GTE: lambda a, b: a >= b,
    ComparisonOperator.LT: lambda a, b: a < b,
    ComparisonOperator.LTE: lambda a, b: a <= b,
    ComparisonOperator.EQ: lambda a, b: a == b,
    ComparisonOperator.NEQ: lambda a, b: a != b,
}


MOMENTUM_POSITIVE_RSI_THRESHOLD = 55.0
MOMENTUM_NEGATIVE_RSI_THRESHOLD = 45.0


def _coerce_momentum(rule: Rule, evidence: ResolvedEvidence) -> object:
    """momentum_state rules can be stated two ways in a strategy: a
    symbolic comparison ("momentum is positive") or a raw numeric one
    ("momentum is above 60"). Both compare against the same RYO evidence
    (data.technicals.rsi_14), so this is the single, named place that
    decides which comparison the rule actually wants, based on the *type*
    of the rule's own stated value... never by silently overriding a
    number the human gave with a bucketed label.

    - rule.value is a string  -> bucket the raw RSI into
      "positive"/"neutral"/"negative" using the two named thresholds below,
      and compare the bucket.
    - rule.value is numeric   -> compare the raw RSI directly; the human
      already gave an exact number, nothing to bucket.
    """
    if rule.metric != "momentum_state" or not isinstance(evidence.value, (int, float)):
        return evidence.value
    if isinstance(rule.value, (int, float)):
        return evidence.value
    rsi = evidence.value
    if rsi > MOMENTUM_POSITIVE_RSI_THRESHOLD:
        return "positive"
    if rsi < MOMENTUM_NEGATIVE_RSI_THRESHOLD:
        return "negative"
    return "neutral"


def evaluate_rule(rule: Rule, evidence: ResolvedEvidence | None) -> RuleResult:
    if rule.status is not RuleStatus.EXECUTABLE:
        return RuleResult(
            rule_id=rule.id,
            status=RuleResultStatus.SKIPPED,
            evidence=evidence,
            explanation=f"rule status is {rule.status.value}: {rule.problem}",
        )

    if evidence is None or not evidence.available:
        note = evidence.note if evidence else "no evidence was resolved for this rule"
        return RuleResult(
            rule_id=rule.id,
            status=RuleResultStatus.UNKNOWN,
            evidence=evidence,
            explanation=f"required evidence unavailable: {note}",
        )

    observed = _coerce_momentum(rule, evidence)
    op_fn = _OPS[rule.operator]
    try:
        passed = op_fn(observed, rule.value)
    except TypeError as exc:
        return RuleResult(
            rule_id=rule.id,
            status=RuleResultStatus.UNKNOWN,
            evidence=evidence,
            explanation=f"evidence value {observed!r} not comparable to rule value {rule.value!r}: {exc}",
        )

    status = RuleResultStatus.PASS if passed else RuleResultStatus.FAIL
    explanation = (
        f"{rule.metric} observed={observed!r} {rule.operator.value} required={rule.value!r} "
        f"-> {status.value}"
    )
    return RuleResult(rule_id=rule.id, status=status, evidence=evidence, explanation=explanation)


def evaluate_strategy(
    strategy: Strategy, evidence_by_rule: dict[str, ResolvedEvidence]
) -> tuple[Decision, tuple[RuleResult, ...]]:
    results = tuple(
        evaluate_rule(rule, evidence_by_rule.get(rule.id)) for rule in strategy.rules
    )

    has_fail = any(r.status is RuleResultStatus.FAIL for r in results)
    has_unknown = any(r.status is RuleResultStatus.UNKNOWN for r in results)
    has_unresolved_rule = any(r.status is RuleResultStatus.SKIPPED for r in results)

    decision: Decision
    if has_fail:
        decision = "BLOCK"
    elif has_unknown or has_unresolved_rule:
        decision = "UNKNOWN"
    else:
        decision = "ALLOW"

    return decision, results
