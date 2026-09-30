"""Maps a rule's metric to where its evidence must come from, then fetches it.

The registry below is deliberately small and explicit. Every entry is backed
by a field that actually exists in RYO's documented response shape:

  - "market_regime" -> MarketOverview.regime, one of
    risk_on | risk_off | rotation | chop (docs/ryo-openapi-subset.json,
    schema MarketOverview) via market_overview.
  - "momentum_state" -> analyze_token's technical read. The guide describes
    analyze_token as returning "calculated technical measurements such as
    RSI(14) and ATR(14)"; this build reads data.technicals.rsi_14 and applies
    a *documented, fixed* threshold (RSI > 55 = "positive momentum", RSI < 45
    = "negative"), not a value the LLM invented -- see compiler.py, the
    threshold lives in code, not in a prompt.
  - "safety_check" is deliberately NOT in this registry. RYO's guide states
    plainly under "Six independent research tools" that the surface "does
    not publish a portfolio-analysis or symbol-only safety tool." A rule
    that requires a safety check therefore has nowhere to resolve from and
    must compile to UNSUPPORTED, not be quietly dropped or guessed at.
  - "allocation_pct" -> EvidenceSource.USER_DECLARED. RYO "cannot read user
    balances, positions, or portfolio state" (same section) -- this is the
    calling application's own responsibility, supplied as an explicit input,
    never invented.
"""
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
            "in the public Nota reference repo) -- the guide's own prose ('calculated "
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
    # --- added after auditing candidate evidence types against real,
    # live-recorded RYO responses (fixtures/recorded/ in the public Nota
    # reference repo). Each entry below was checked against all five
    # questions: (1) can RYO actually provide it, (2) can the condition be
    # expressed deterministically, (3) can the compiler express it without
    # inventing a threshold, (4) can the evaluator verify it from returned
    # evidence, (5) can the receipt cite the exact evidence path. Only
    # entries that passed all five were added. See docs/LIMITATIONS.md for
    # the full audit, including candidates that did NOT pass and why.
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

# Candidates that were audited against the same five questions and did NOT
# pass -- recorded here, not silently dropped, so the same case isn't
# re-litigated from scratch later:
#
# - Token narrative / catalysts / risks / token_profile analysis text
#   (analyze_token.data.intelligence, deep_analysis.data.token_profile):
#   real fields, but free text, not a value a deterministic operator can
#   compare against. Fails question 3 (compiler would have to judge prose)
#   and question 4 (evaluator can't verify prose against a threshold).
# - Cross-token comparison winner (compare_tokens.data.winner /
#   conclusion.pick): passes all five questions in principle, but a rule
#   like "only buy SOL if it beats BTC and ETH" needs a *set* of comparison
#   symbols, and schema.py's Rule has exactly one `asset` field -- adding
#   this cleanly needs a Rule/EvidenceRequirement shape change, not just a
#   registry entry. Real candidate for a future pass; out of scope for an
#   evidence-registry audit that isn't supposed to redesign the schema.
# - Derivatives (deep_analysis.data.derivatives.funding_rate_bps,
#   squeeze_risk, veto): passes all five questions too (confirmed live
#   fields), deferred only to keep this pass's diff reviewable -- it needs
#   its own MetricSpec plus handling for the field legitimately being
#   `null` per-token (the recording shows long_short_ratio: null for SOL),
#   which the other four additions above don't need to handle.
# - News/claim verification: RYO provides no such tool at all (confirmed:
#   none of the six Builder MCP tools touch news; the guide is explicit
#   that a news source, if used, is the builder's own responsibility).
#   Fails question 1 outright. A rule needing this stays UNSUPPORTED.


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
