import os

import pytest

RYO_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


@pytest.mark.skipif(
    not RYO_ANTHROPIC_KEY,
    reason="SKIPPED: ANTHROPIC_API_KEY not configured (set it to run this for real)",
)
def test_translate_strategy_against_the_live_anthropic_api():
    from strategy_compiler.llm import AnthropicLLM

    llm = AnthropicLLM()
    rules = llm.translate_strategy("Buy SOL when SOL momentum is above 50.")
    assert isinstance(rules, list)
    assert len(rules) >= 1
    assert "metric" in rules[0]


def test_anthropic_llm_refuses_to_construct_without_a_key(monkeypatch):
    from strategy_compiler.llm import AnthropicLLM

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        AnthropicLLM(api_key=None)
