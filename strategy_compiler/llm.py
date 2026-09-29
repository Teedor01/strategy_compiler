from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx

TRANSLATION_SYSTEM_PROMPT = """\
You convert a human's informal trading/investment strategy into a list of \
candidate rules. You do not decide whether any rule is true or false, and \
you do not invent numeric thresholds the human did not state.

For each distinct constraint you find in the text, return an object with:
  raw_text: the exact clause this came from
  asset: the token symbol it applies to, or null if it applies to the whole strategy
  metric: a short machine-friendly name for what's being measured
          (e.g. "momentum_state", "market_regime", "allocation_pct", "safety_check")
  operator: one of ">", ">=", "<", "<=", "==", "!=", or null if the human gave no
            comparable operator
  value: the threshold value IF AND ONLY IF the human explicitly stated a number
         or an unambiguous discrete state (e.g. "bearish"). If the human used a
         vague qualitative word with no defined threshold ("strong", "too much",
         "looking bad") set value to null and explain why in ambiguity_note --
         do not guess a number to fill the gap.
  ambiguity_note: null if the rule is fully specified, otherwise a short
                  description of exactly what is missing.

Return ONLY a JSON array of these objects. No prose, no markdown fences.
"""


class LLMProvider(Protocol):
    model_name: str

    def translate_strategy(self, strategy_text: str) -> list[dict[str, Any]]:
        """Return the model's best-effort list of candidate rule objects.
        Must not raise on ambiguity -- ambiguity is reported via
        ambiguity_note, not by refusing to answer.
        """
        ...


class AnthropicLLM:
    """Real implementation against Anthropic's public Messages API.

    Implemented against the documented endpoint and request shape
    (https://api.anthropic.com/v1/messages, model + max_tokens + messages),
    matching this project's own "bring your own AI model" requirement.
    Not exercised in this environment: no ANTHROPIC_API_KEY is set here, so
    this class has been read-reviewed but not run. See docs/LIMITATIONS.md.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        self.model_name = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. AnthropicLLM is implemented but "
                "cannot be constructed without a key -- this is intentional, "
                "not a bug: the project must not silently fall back to a "
                "fixture and call it a live translation."
            )
        self._client = httpx.Client(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=60.0,
        )

    def translate_strategy(self, strategy_text: str) -> list[dict[str, Any]]:
        response = self._client.post(
            "/v1/messages",
            json={
                "model": self.model_name,
                "max_tokens": 2000,
                "system": TRANSLATION_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": strategy_text}],
            },
        )
        response.raise_for_status()
        body = response.json()
        text = "".join(
            block.get("text", "") for block in body.get("content", []) if block.get("type") == "text"
        )
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise TypeError("expected a JSON array of rule objects")
        return parsed


class FixtureLLM:
    """Deterministic test double. Not a language model.

    Holds exact-match canned translations for the ugly test sentences named
    in the project brief (see tests/test_compiler.py), so the compiler's
    ambiguity-handling logic can be exercised without any network access or
    API key. Anything not in the table raises, loudly, rather than guessing...
     a silent fallback here would be exactly the kind of "fake a response"
    behavior the brief explicitly forbids.
    """

    model_name = "fixture:deterministic-test-double"

    def __init__(self, canned: dict[str, list[dict[str, Any]]]):
        self._canned = canned

    def translate_strategy(self, strategy_text: str) -> list[dict[str, Any]]:
        key = strategy_text.strip()
        if key not in self._canned:
            raise KeyError(
                f"FixtureLLM has no canned translation for: {key!r}. "
                "This is not a language model -- it only knows the exact "
                "strings registered in fixtures.py."
            )
        return self._canned[key]
