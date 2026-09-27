from __future__ import annotations

import json
import os
import sys

import typer

from .fixtures import DEMO_FIXTURE_LLM
from .receipt import receipt_to_dict
from .ryo_client import FixtureRyoClient, RyoClient, RyoConfigError

app = typer.Typer(help="Strategy Compiler CLI")


def _build_ryo(source: str) -> object:
    if source == "live":
        try:
            return RyoClient()
        except RyoConfigError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    if source == "fixture":
        from .fixtures import load_envelope_fixtures

        return FixtureRyoClient(load_envelope_fixtures())
    raise typer.BadParameter("source must be 'live' or 'fixture'")


def _build_llm(source: str):
    if source == "live":
        from .llm import AnthropicLLM

        try:
            return AnthropicLLM()
        except RuntimeError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    if source == "fixture":
        return DEMO_FIXTURE_LLM
    raise typer.BadParameter("source must be 'live' or 'fixture'")


@app.command()
def decide(
    strategy_text: str = typer.Argument(..., help="The strategy, in plain English"),
    llm_source: str = typer.Option("fixture", help="'live' (needs ANTHROPIC_API_KEY) or 'fixture'"),
    ryo_source: str = typer.Option("fixture", help="'live' (needs RYO_MCP_URL/RYO_MCP_KEY) or 'fixture'"),
    allocation_pct: float = typer.Option(None, help="Proposed position size as fraction of portfolio, e.g. 0.15"),
):
    """Run the full pipeline: compile -> resolve -> evaluate -> receipt."""
    from .decide import decide as run_decide

    llm = _build_llm(llm_source)
    ryo = _build_ryo(ryo_source)
    user_declared = {}
    if allocation_pct is not None:
        user_declared["allocation_pct"] = allocation_pct

    receipt = run_decide(strategy_text, llm=llm, ryo=ryo, user_declared=user_declared)
    print(json.dumps(receipt_to_dict(receipt), indent=2))

    if llm_source == "fixture" or ryo_source == "fixture":
        typer.secho(
            "\n[note] this run used a labelled fixture for "
            + ", ".join(
                s for s, used in (("LLM", llm_source == "fixture"), ("RYO", ryo_source == "fixture")) if used
            )
            + " -- see docs/LIMITATIONS.md. compiler_model and sources above show exactly which.",
            fg=typer.colors.YELLOW,
            err=True,
        )


@app.command()
def skill_spec():
    """Print the Track 3 SkillDefinition-shaped spec for compile_strategy."""
    from .skill import SKILL_DEFINITION

    print(json.dumps(SKILL_DEFINITION, indent=2))


if __name__ == "__main__":
    app()
