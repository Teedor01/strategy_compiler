from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .envelope import MissingEvidence, RyoEnvelope
from .ryo_client import RyoToolError
from .schema import EvidenceRequirement, EvidenceSource, ResolvedEvidence, Rule

RyoCaller = Callable[[str, dict[str, Any]], RyoEnvelope]


@dataclass(frozen=True)
class MetricSpec:
    source: EvidenceSource
    ryo_tool: str | None = None
    ryo_path: str | None = None
    build_args: Callable[[Rule], dict[str, Any]] | None = None
    description: str = ""


REGISTRY: dict[str, MetricSpec] = {
    "market_regime": MetricSpec(
        source=EvidenceSource.RYO_TOOL,
        ryo_tool="market_overview",
        ryo_path="regime",
        build_args=lambda rule: {},
        description="RYO market_overview.data.regime (risk_on | risk_off | rotation | chop)",
    ),
    "momentum_state": MetricSpec(
        source=EvidenceSource.RYO_TOOL,
        ryo_tool="analyze_token",
        ryo_path="technicals.rsi_14",
        build_args=lambda rule: {"symbol": rule.asset},
        description="RYO analyze_token.data.technicals.rsi_14, thresholded in code (>55 positive, <45 negative)",
    ),
    "allocation_pct": MetricSpec(
        source=EvidenceSource.USER_DECLARED,
        description=(
            "Proposed position size as a percentage of portfolio value. "
            "RYO does not read portfolio state (MCP-Builder-Guide.md); the "
            "calling application must supply this explicitly."
        ),
    ),
}


def known_metric(metric: str) -> bool:
    return metric in REGISTRY


def build_requirement(rule: Rule) -> EvidenceRequirement:
    spec = REGISTRY.get(rule.metric or "")
    if spec is None:
        raise KeyError(f"'{rule.metric}' is not in the evidence registry")
    args = spec.build_args(rule) if spec.build_args else {}
    return EvidenceRequirement(
        metric=rule.metric or "",
        source=spec.source,
        ryo_tool=spec.ryo_tool,
        ryo_args=args,
        ryo_path=spec.ryo_path,
        description=spec.description,
    )


def resolve(
    rule: Rule,
    ryo_call: RyoCaller,
    *,
    user_declared: dict[str, Any] | None = None,
) -> ResolvedEvidence:
    """Fetch (or look up) the evidence one EXECUTABLE rule needs.

    Never raises for "evidence unavailable"... that is a normal, expected
    outcome represented by `available=False`, which evaluator.py turns into
    RuleResultStatus.UNKNOWN. It only raises for programmer errors (an
    unknown metric slipping past compiler.py, which should never happen).
    """
    requirement = build_requirement(rule)
    user_declared = user_declared or {}

    if requirement.source is EvidenceSource.USER_DECLARED:
        if requirement.metric in user_declared:
            return ResolvedEvidence(
                rule_id=rule.id,
                requirement=requirement,
                available=True,
                value=user_declared[requirement.metric],
                note="Supplied directly by the calling application, not RYO "
                "(RYO does not read portfolio/user state).",
            )
        return ResolvedEvidence(
            rule_id=rule.id,
            requirement=requirement,
            available=False,
            note=f"'{requirement.metric}' was not supplied by the caller; "
            "RYO cannot supply it either.",
        )

    # EvidenceSource.RYO_TOOL
    try:
        envelope = ryo_call(requirement.ryo_tool, requirement.ryo_args)
    except RyoToolError as exc:
        return ResolvedEvidence(
            rule_id=rule.id,
            requirement=requirement,
            available=False,
            note=f"RYO call to {requirement.ryo_tool} failed: {exc}",
        )

    if envelope.status == "unavailable":
        return ResolvedEvidence(
            rule_id=rule.id,
            requirement=requirement,
            available=False,
            raw_envelope=envelope.raw,
            data_mode=envelope.data_mode,
            as_of=envelope.as_of,
            note=f"{requirement.ryo_tool} returned status=unavailable",
        )

    try:
        value = envelope.get_path(requirement.ryo_path)
    except MissingEvidence as exc:
        return ResolvedEvidence(
            rule_id=rule.id,
            requirement=requirement,
            available=False,
            raw_envelope=envelope.raw,
            data_mode=envelope.data_mode,
            as_of=envelope.as_of,
            note=str(exc),
        )

    return ResolvedEvidence(
        rule_id=rule.id,
        requirement=requirement,
        available=True,
        value=value,
        raw_envelope=envelope.raw,
        data_mode=envelope.data_mode,
        as_of=envelope.as_of,
    )
