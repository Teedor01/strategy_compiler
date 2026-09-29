from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class MissingEvidence(Exception):
    """Raised when a dotted path is looked up but the value is null/absent.

    This is intentionally a distinct exception from a Python KeyError so that
    resolver.py can tell "the field doesn't exist in the schema" (a bug) apart
    from "RYO returned null/unavailable for this field" (an UNKNOWN evidence
    result, which is a normal and expected outcome, not an error).
    """


@dataclass(frozen=True)
class RyoEnvelope:
    schema_version: str | None
    tool: str | None
    status: str  
    data_mode: str | None  
    as_of: str | None
    request: dict[str, Any]
    data: dict[str, Any]
    summary: dict[str, Any]
    availability: dict[str, Any]
    warnings: list[Any]
    raw: dict[str, Any]

    def get_path(self, dotted_path: str) -> Any:
        """Look up a dotted path inside `data`. Raises MissingEvidence if the
        value is genuinely absent or null... callers must not substitute a
        default, per the guide's explicit "never convert to zero" rule.
        """
        node: Any = self.data
        for part in dotted_path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                raise MissingEvidence(
                    f"path '{dotted_path}' not present in {self.tool} data envelope"
                )
        if node is None:
            raise MissingEvidence(
                f"path '{dotted_path}' is null in {self.tool} data envelope "
                "(RYO returned no measurement... do not treat as 0/False)"
            )
        return node


def parse_envelope(raw: dict[str, Any]) -> RyoEnvelope:
    """Parse a raw JSON object into a RyoEnvelope.

    Accepts the object exactly as documented: either the REST body directly,
    or (per the guide's "Parse MCP text content" example) the JSON already
    extracted from the MCP `result.content[].text` string... extraction from
    the MCP transport wrapper itself is the caller's job (see ryo_client.py),
    this function only understands the envelope shape itself.
    """
    return RyoEnvelope(
        schema_version=raw.get("schema_version"),
        tool=raw.get("tool"),
        status=raw.get("status", "unavailable"),
        data_mode=raw.get("data_mode"),
        as_of=raw.get("as_of"),
        request=raw.get("request") or {},
        data=raw.get("data") or {},
        summary=raw.get("summary") or {},
        availability=raw.get("availability") or {},
        warnings=raw.get("warnings") or [],
        raw=raw,
    )
