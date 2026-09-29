from __future__ import annotations

import time
from typing import Any

from .decide import decide
from .llm import LLMProvider
from .receipt import receipt_to_dict
from .ryo_client import RyoClient

SKILL_DEFINITION: dict[str, Any] = {
    "name": "compile_strategy",
    "description": (
        "Compile a natural-language trading/investment strategy into explicit "
        "constraints, resolve the evidence those constraints need from RYO's "
        "read-only market tools (or from caller-declared portfolio state RYO "
        "cannot see), evaluate every constraint deterministically, and return "
        "an auditable ALLOW/BLOCK/UNKNOWN receipt naming exactly which rule "
        "decided it."
    ),
    "args": [
        {
            "name": "strategy_text",
            "type": "string",
            "required": True,
            "description": "The strategy in the human's own words, e.g. "
            "'Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 20% of the portfolio.'",
        },
        {
            "name": "user_declared",
            "type": "object",
            "required": False,
            "description": "Portfolio/account state RYO cannot read on its own, "
            "e.g. {\"allocation_pct\": 0.15} for the proposed SOL position as a "
            "fraction of the portfolio.",
        },
    ],
    "requires_guard": False,
    "xp": 0,
}


def invoke(args: dict[str, Any], *, llm: LLMProvider, ryo: RyoClient) -> dict[str, Any]:
    """Shaped as a SkillCallResponse: {name, status, result, latency_ms}."""
    started = time.monotonic()
    strategy_text = args.get("strategy_text")
    if not strategy_text or not isinstance(strategy_text, str):
        return {
            "name": SKILL_DEFINITION["name"],
            "status": "error",
            "result": {"error": "strategy_text (string) is required"},
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    user_declared = args.get("user_declared") or {}
    if not isinstance(user_declared, dict):
        return {
            "name": SKILL_DEFINITION["name"],
            "status": "error",
            "result": {"error": "user_declared must be an object/dict if provided"},
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    try:
        receipt = decide(strategy_text, llm=llm, ryo=ryo, user_declared=user_declared)
    except Exception as exc:  # noqa: BLE001 - surfaced to caller, not swallowed
        return {
            "name": SKILL_DEFINITION["name"],
            "status": "error",
            "result": {"error": str(exc)},
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    return {
        "name": SKILL_DEFINITION["name"],
        "status": "success",
        "result": receipt_to_dict(receipt),
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
