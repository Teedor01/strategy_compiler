from __future__ import annotations

from typing import Any

from . import resolver
from .compiler import compile_strategy
from .evaluator import evaluate_strategy
from .llm import LLMProvider
from .receipt import build_receipt
from .ryo_client import RyoClient
from .schema import Receipt, RuleStatus


def decide(
    strategy_text: str,
    *,
    llm: LLMProvider,
    ryo: RyoClient,
    user_declared: dict[str, Any] | None = None,
) -> Receipt:
    strategy = compile_strategy(strategy_text, llm)

    evidence_by_rule = {}
    for rule in strategy.rules:
        if rule.status is not RuleStatus.EXECUTABLE:
            continue
        evidence_by_rule[rule.id] = resolver.resolve(
            rule, ryo.call, user_declared=user_declared
        )

    decision, results = evaluate_strategy(strategy, evidence_by_rule)
    return build_receipt(strategy, decision, results)
