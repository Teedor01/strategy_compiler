"""Typed schema for Strategy Compiler.

These types are the contract between the three stages that must never blur
into each other:

    LLM translates human language  -> Strategy (this module)
    Deterministic code resolves evidence -> ResolvedEvidence (this module)
    Deterministic code evaluates constraints -> RuleResult / Decision (this module)

Nothing in this module calls an LLM or a network. It is pure data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class RuleStatus(str, Enum):
    """What the compiler decided about one extracted rule, before evaluation."""

    EXECUTABLE = "EXECUTABLE"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICTING = "CONFLICTING"


class EvidenceSource(str, Enum):
    """Where a rule's required evidence must come from.

    RYO's guide is explicit that the platform is read-only market research and
    "does not read user balances, positions, or portfolio state" (MCP-Builder-Guide.md,
    "Six independent research tools"). So a rule like "never exceed 20% of the
    portfolio" cannot be resolved from RYO at all -- it has to be resolved from
    state the builder's own application declares. Conflating the two would be a
    correctness bug, not a style choice, so it is a first-class field here.
    """

    RYO_TOOL = "ryo_tool"
    USER_DECLARED = "user_declared"


class ComparisonOperator(str, Enum):
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NEQ = "!="


@dataclass(frozen=True)
class EvidenceRequirement:
    """What a rule needs in order to be checked, and where that should come from."""

    metric: str  # e.g. "sol.momentum_state", "btc.regime", "position.allocation_pct"
    source: EvidenceSource
    # Only meaningful when source == RYO_TOOL:
    ryo_tool: str | None = None
    ryo_args: dict[str, Any] = field(default_factory=dict)
    ryo_path: str | None = None  # dotted path into the tool's `data` envelope field
    description: str = ""


@dataclass(frozen=True)
class Rule:
    """One machine-checkable constraint extracted from the human strategy."""

    id: str
    raw_text: str  # the exact clause of the original strategy this came from
    status: RuleStatus
    asset: str | None = None
    metric: str | None = None
    operator: ComparisonOperator | None = None
    value: Any = None
    evidence: EvidenceRequirement | None = None
    problem: str | None = None  # populated when NEEDS_CLARIFICATION / UNSUPPORTED / CONFLICTING
    conflicts_with: tuple[str, ...] = field(default_factory=tuple)  # other rule ids


@dataclass(frozen=True)
class Strategy:
    """The compiler's structured output for one natural-language strategy."""

    raw_text: str
    rules: tuple[Rule, ...]
    compiler_model: str  # e.g. "claude-sonnet-4-6" or "fixture:deterministic-test-double"
    compiled_at: str  # ISO-8601 UTC


class RuleResultStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"  # required evidence could not be obtained
    SKIPPED = "SKIPPED"  # rule itself was not EXECUTABLE (clarification/unsupported/conflicting)


@dataclass(frozen=True)
class ResolvedEvidence:
    """What was actually retrieved (or not) for one rule's requirement."""

    rule_id: str
    requirement: EvidenceRequirement
    available: bool
    value: Any = None
    raw_envelope: dict[str, Any] | None = None  # the full RYO envelope, if source == ryo_tool
    data_mode: str | None = None  # RYO's data_mode: live | mixed | simulated | unknown
    as_of: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: RuleResultStatus
    evidence: ResolvedEvidence | None
    explanation: str


Decision = Literal["ALLOW", "BLOCK", "UNKNOWN"]


@dataclass(frozen=True)
class Receipt:
    """The final, auditable output of one strategy evaluation."""

    trace_id: str
    decision: Decision
    strategy: Strategy
    rule_results: tuple[RuleResult, ...]
    blocking_rule_ids: tuple[str, ...]
    unresolved_rule_ids: tuple[str, ...]  # NEEDS_CLARIFICATION / UNSUPPORTED / CONFLICTING
    evaluator_version: str
    generated_at: str
    sources: tuple[str, ...]  # human-readable list of where evidence came from
