import json
from pathlib import Path

from strategy_compiler.skill import SKILL_DEFINITION, invoke
from strategy_compiler.fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from strategy_compiler.ryo_client import FixtureRyoClient

OPENAPI_SUBSET = Path(__file__).parent.parent / "docs" / "ryo-openapi-subset.json"


def _schema_field_names(schema_name: str) -> set[str]:
    spec = json.loads(OPENAPI_SUBSET.read_text())
    return set(spec["schemas"][schema_name]["properties"].keys())


def test_skill_definition_only_uses_real_schema_fields():
    if not OPENAPI_SUBSET.exists():
        return  
    allowed = _schema_field_names("SkillDefinition")
    assert set(SKILL_DEFINITION.keys()) <= allowed, (
        f"compile_strategy's SkillDefinition uses field(s) not in RYO's real "
        f"schema: {set(SKILL_DEFINITION.keys()) - allowed}"
    )
    required = {"name", "description"}
    assert required <= set(SKILL_DEFINITION.keys())


def test_skill_args_only_use_real_schema_fields():
    if not OPENAPI_SUBSET.exists():
        return
    allowed = _schema_field_names("SkillArgSchema")
    for arg in SKILL_DEFINITION["args"]:
        assert set(arg.keys()) <= allowed, f"arg {arg['name']} uses unknown field(s): {set(arg.keys()) - allowed}"


def test_read_only_skill_does_not_require_guard():
    assert SKILL_DEFINITION["requires_guard"] is False


def test_invoke_returns_skill_call_response_shape():
    ryo = FixtureRyoClient(load_envelope_fixtures())
    result = invoke(
        {"strategy_text": "Buy SOL when SOL momentum is above 50.", "user_declared": {}},
        llm=DEMO_FIXTURE_LLM,
        ryo=ryo,
    )
    assert set(result.keys()) <= {"name", "status", "result", "latency_ms", "xp", "guard_decision"}
    assert result["name"] == "compile_strategy"
    assert result["status"] == "success"
    assert result["result"]["decision"] in {"ALLOW", "BLOCK", "UNKNOWN"}


def test_invoke_errors_on_missing_strategy_text():
    ryo = FixtureRyoClient(load_envelope_fixtures())
    result = invoke({}, llm=DEMO_FIXTURE_LLM, ryo=ryo)
    assert result["status"] == "error"
