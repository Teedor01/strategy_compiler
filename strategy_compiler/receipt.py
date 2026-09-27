from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

from .evaluator import EVALUATOR_VERSION
from .schema import Decision, Receipt, RuleResult, RuleResultStatus, RuleStatus, Strategy


def _trace_id(strategy: Strategy, results: tuple[RuleResult, ...]) -> str:
    payload = {
        "raw_text": strategy.raw_text,
        "compiler_model": strategy.compiler_model,
        "rules": [
            {
                "id": r.id,
                "status": r.status.value,
                "asset": r.asset,
                "metric": r.metric,
                "operator": r.operator.value if r.operator else None,
                "value": r.value,
            }
            for r in strategy.rules
        ],
        "results": [
            {"rule_id": r.rule_id, "status": r.status.value, "value": (r.evidence.value if r.evidence else None)}
            for r in results
        ],
        "evaluator_version": EVALUATOR_VERSION,
    }
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def build_receipt(strategy: Strategy, decision: Decision, results: tuple[RuleResult, ...]) -> Receipt:
    blocking = tuple(r.rule_id for r in results if r.status is RuleResultStatus.FAIL)
    unresolved = tuple(
        rule.id for rule in strategy.rules if rule.status is not RuleStatus.EXECUTABLE
    )

    sources: set[str] = set()
    for r in results:
        if r.evidence is None:
            continue
        if r.evidence.requirement.source.value == "ryo_tool":
            label = f"RYO:{r.evidence.requirement.ryo_tool}"
            if r.evidence.data_mode:
                label += f" (data_mode={r.evidence.data_mode})"
            sources.add(label)
        else:
            sources.add("user_declared")

    return Receipt(
        trace_id=_trace_id(strategy, results),
        decision=decision,
        strategy=strategy,
        rule_results=results,
        blocking_rule_ids=blocking,
        unresolved_rule_ids=unresolved,
        evaluator_version=EVALUATOR_VERSION,
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        sources=tuple(sorted(sources)),
    )


def receipt_to_dict(receipt: Receipt) -> dict[str, Any]:
    """JSON-serializable form, shaped close to the brief's own sketch."""
    return {
        "trace_id": receipt.trace_id,
        "decision": receipt.decision,
        "strategy_text": receipt.strategy.raw_text,
        "compiler_model": receipt.strategy.compiler_model,
        "compiled_at": receipt.strategy.compiled_at,
        "generated_at": receipt.generated_at,
        "evaluator_version": receipt.evaluator_version,
        "rules": [
            {
                "id": rule.id,
                "raw_text": rule.raw_text,
                "status": rule.status.value,
                "asset": rule.asset,
                "metric": rule.metric,
                "operator": rule.operator.value if rule.operator else None,
                "value": rule.value,
                "problem": rule.problem,
                "conflicts_with": list(rule.conflicts_with),
            }
            for rule in receipt.strategy.rules
        ],
        "rule_results": [
            {
                "rule_id": r.rule_id,
                "status": r.status.value,
                "explanation": r.explanation,
                "evidence": (
                    None
                    if r.evidence is None
                    else {
                        "metric": r.evidence.requirement.metric,
                        "source": r.evidence.requirement.source.value,
                        "available": r.evidence.available,
                        "value": r.evidence.value,
                        "data_mode": r.evidence.data_mode,
                        "as_of": r.evidence.as_of,
                        "note": r.evidence.note,
                    }
                ),
            }
            for r in receipt.rule_results
        ],
        "blocking_rule_ids": list(receipt.blocking_rule_ids),
        "unresolved_rule_ids": list(receipt.unresolved_rule_ids),
        "sources": list(receipt.sources),
    }
