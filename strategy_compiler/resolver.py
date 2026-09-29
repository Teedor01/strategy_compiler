from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
        ryo_path="technical_analysis.rsi_14",
        build_args=lambda rule: {"symbol": rule.asset},
        description=(
            "RYO analyze_token.data.technical_analysis.rsi_14, thresholded in code "
            "(>55 positive, <45 negative). Path confirmed against a real, "
            "live-recorded analyze_token response (fixtures/recorded/analyze_token/SOL.json "
            "in the public Nota reference repo)... the guide's own prose ('calculated "
            "technical measurements such as RSI(14) and ATR(14)') never states the exact "
            "JSON path, and no schema for analyze_token's payload exists in "
            "ryo-openapi-subset.json either. The first version of this registry used "
            "'technicals.rsi_14', an unverified guess from the prose alone -- wrong key name. "
            "RYO's real response also includes a pre-computed data.technical_analysis.trend "
            "('up'/'down'), a cleaner symbolic source than bucketing RSI ourselves; noted in "
            "docs/LIMITATIONS.md as a candidate improvement, not adopted here to keep this a "
            "verified-path fix rather than a design change."
        ),
    ),
    "allocation_pct": MetricSpec(
        source=EvidenceSource.USER_DECLARED,
        description=(
            "Proposed position size as a percentage of portfolio value. "
            "RYO does not read portfolio state (MCP-Builder-Guide.md); the "
            "calling application must supply this explicitly."
        ),
    ),

    "price_usd": MetricSpec(
        source=EvidenceSource.RYO_TOOL,
        ryo_tool="analyze_token",
        ryo_path="market.price_usd",
        build_args=lambda rule: {"symbol": rule.asset},
        description=(
            "RYO analyze_token.data.market.price_usd -- confirmed against a real, "
            "live-recorded analyze_token/SOL response. Same tool call as "
            "momentum_state, so a strategy using both costs no extra RYO call."
        ),
    ),
    "change_24h_pct": MetricSpec(
        source=EvidenceSource.RYO_TOOL,
        ryo_tool="analyze_token",
        ryo_path="performance.change_24h_pct",
        build_args=lambda rule: {"symbol": rule.asset},
        description=(
            "RYO analyze_token.data.performance.change_24h_pct -- confirmed live. "
            "NOTE: deep_analysis uses a differently-named field for the same "
            "concept (performance.h24, per the same recording) -- this registry "
            "deliberately pins to analyze_token's naming only, so a rule never "
            "silently reads the wrong tool's field under an assumed-shared name."
        ),
    ),
    "market_cap_rank": MetricSpec(
        source=EvidenceSource.RYO_TOOL,
        ryo_tool="analyze_token",
        ryo_path="asset.rank",
        build_args=lambda rule: {"symbol": rule.asset},
        description="RYO analyze_token.data.asset.rank (integer) -- confirmed live (SOL: 7).",
    ),
    "fear_greed_index": MetricSpec(
        source=EvidenceSource.RYO_TOOL,
        ryo_tool="market_overview",
        ryo_path="sentiment.fear_greed_index",
        build_args=lambda rule: {},
        description=(
            "RYO market_overview.data.sentiment.fear_greed_index (0-100) -- confirmed "
            "live (74.0, labelled 'greed' the same day). Same tool call as "
            "market_regime, no extra RYO call for a strategy using both."
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

    Never raises for "evidence unavailable" -- that is a normal, expected
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
