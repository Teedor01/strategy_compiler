from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .decide import decide as run_decide
from .fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from .receipt import receipt_to_dict
from .ryo_client import FixtureRyoClient
from .skill import SKILL_DEFINITION

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Strategy Compiler")


class DecideRequest(BaseModel):
    strategy_text: str
    allocation_pct: float | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/skill")
def skill_spec() -> dict[str, Any]:
    return SKILL_DEFINITION


@app.post("/api/decide")
def api_decide(req: DecideRequest) -> dict[str, Any]:
    """Runs the pipeline against fixture LLM + fixture RYO by default.

    This endpoint is intentionally wired to the labelled fixtures, not to
    live services, because this environment has neither ANTHROPIC_API_KEY
    nor RYO_MCP_KEY configured. Swapping in AnthropicLLM()/RyoClient() is a
    two-line change in this function once real credentials exist -- see
    docs/LIMITATIONS.md for exactly what that swap does and does not change
    about everything else in this project.
    """
    llm = DEMO_FIXTURE_LLM
    ryo = FixtureRyoClient(load_envelope_fixtures())
    user_declared = {}
    if req.allocation_pct is not None:
        user_declared["allocation_pct"] = req.allocation_pct

    receipt = run_decide(req.strategy_text, llm=llm, ryo=ryo, user_declared=user_declared)
    return receipt_to_dict(receipt)
