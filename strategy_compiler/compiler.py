from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import Any

from .llm import LLMProvider
from .resolver import known_metric
from .schema import ComparisonOperator, Rule, RuleStatus, Strategy

_METRIC_ALIASES = {
    "momentum": "momentum_state",
    "momentum_state": "momentum_state",
    "regime": "market_regime",
    "market_regime": "market_regime",
    "trend": "market_regime",
    "allocation": "allocation_pct",
    "allocation_pct": "allocation_pct",
    "portfolio_allocation": "allocation_pct",
    "safety": "safety_check",
    "safety_check": "safety_check",
}


def _normalize_metric(raw_metric: str | None) -> str | None:
    if raw_metric is None:
        return None
    return _METRIC_ALIASES.get(raw_metric.strip().lower(), raw_metric.strip().lower())


def _normalize_operator(raw_operator: str | None) -> ComparisonOperator | None:
    if raw_operator is None:
        return None
    try:
        return ComparisonOperator(raw_operator.strip())
    except ValueError:
        return None


def _classify_single(rule_id: str, raw: dict[str, Any]) -> Rule:
    raw_text = raw.get("raw_text", "")
    asset = (raw.get("asset") or None)
    if isinstance(asset, str):
        asset = asset.upper()
    metric = _normalize_metric(raw.get("metric"))
    operator = _normalize_operator(raw.get("operator"))
    value = raw.get("value")
    ambiguity_note = raw.get("ambiguity_note")

    if value is None or operator is None or ambiguity_note:
        problem = ambiguity_note or (
            "no comparable operator/value was extracted from the text"
        )
        return Rule(
            id=rule_id,
            raw_text=raw_text,
            status=RuleStatus.NEEDS_CLARIFICATION,
            asset=asset,
            metric=metric,
            operator=operator,
            value=value,
            problem=problem,
        )


    if metric is None or not known_metric(metric):
        return Rule(
            id=rule_id,
            raw_text=raw_text,
            status=RuleStatus.UNSUPPORTED,
            asset=asset,
            metric=metric,
            operator=operator,
            value=value,
            problem=(
                f"no evidence source is registered for metric '{metric}'. "
                "RYO's six tools and this build's user-declared fields do "
                "not cover it."
            ),
        )

    return Rule(
        id=rule_id,
        raw_text=raw_text,
        status=RuleStatus.EXECUTABLE,
        asset=asset,
        metric=metric,
        operator=operator,
        value=value,
    )


def _numeric_contradiction(a: Rule, b: Rule) -> bool:
    """True if a and b, both EXECUTABLE on the same asset+metric, cannot
    both be satisfied by any value... checked with plain interval
    arithmetic, not a model opinion.
    """
    if not (isinstance(a.value, (int, float)) and isinstance(b.value, (int, float))):
        if a.operator is ComparisonOperator.EQ and b.operator is ComparisonOperator.NEQ:
            return a.value == b.value
        if a.operator is ComparisonOperator.NEQ and b.operator is ComparisonOperator.EQ:
            return a.value == b.value
        if a.operator is ComparisonOperator.EQ and b.operator is ComparisonOperator.EQ:
            return a.value != b.value
        return False

    def lower_bound(rule: Rule) -> float | None:
        if rule.operator is ComparisonOperator.GT:
            return rule.value + 1e-9
        if rule.operator is ComparisonOperator.GTE:
            return rule.value
        return None

    def upper_bound(rule: Rule) -> float | None:
        if rule.operator is ComparisonOperator.LT:
            return rule.value - 1e-9
        if rule.operator is ComparisonOperator.LTE:
            return rule.value
        return None

    lowers = [b for b in (lower_bound(a), lower_bound(b)) if b is not None]
    uppers = [b for b in (upper_bound(a), upper_bound(b)) if b is not None]
    if lowers and uppers and max(lowers) > min(uppers):
        return True

    if a.operator is ComparisonOperator.EQ and b.operator is ComparisonOperator.EQ:
        return a.value != b.value
    return False


def _mark_conflicts(rules: list[Rule]) -> list[Rule]:
    executable = [r for r in rules if r.status is RuleStatus.EXECUTABLE]
    conflicts: dict[str, set[str]] = {r.id: set() for r in executable}

    for i, a in enumerate(executable):
        for b in executable[i + 1:]:
            if a.asset == b.asset and a.metric == b.metric and _numeric_contradiction(a, b):
                conflicts[a.id].add(b.id)
                conflicts[b.id].add(a.id)

    updated: list[Rule] = []
    for r in rules:
        if r.status is RuleStatus.EXECUTABLE and conflicts.get(r.id):
            updated.append(
                replace(
                    r,
                    status=RuleStatus.CONFLICTING,
                    conflicts_with=tuple(sorted(conflicts[r.id])),
                    problem=(
                        f"contradicts rule(s) {', '.join(sorted(conflicts[r.id]))} on the "
                        f"same asset ({r.asset}) and metric ({r.metric}): no value could "
                        "satisfy both"
                    ),
                )
            )
        else:
            updated.append(r)
    return updated


def compile_strategy(strategy_text: str, llm: LLMProvider) -> Strategy:
    """The only function that touches an LLM in the compile step.

    strategy_text -> llm.translate_strategy() -> classify each candidate ->
    detect conflicts across the classified set -> Strategy.
    """
    raw_rules = llm.translate_strategy(strategy_text)
    rules = [_classify_single(f"rule_{i + 1}", raw) for i, raw in enumerate(raw_rules)]
    rules = _mark_conflicts(rules)
    return Strategy(
        raw_text=strategy_text,
        rules=tuple(rules),
        compiler_model=llm.model_name,
        compiled_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    )
