import json
from pathlib import Path

from strategy_compiler.fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from strategy_compiler.ryo_client import FixtureRyoClient
from strategy_compiler.skill import SKILL_DEFINITION, invoke

OPENAPI_SUBSET = Path(__file__).parent.parent / "docs" / "ryo-openapi-subset.json"


def _schema_field_names(schema_name: str) -> set[str]:
    spec = json.loads(OPENAPI_SUBSET.read_text())
    return set(spec["schemas"][schema_name]["properties"].keys())


def test_skill_definition_only_uses_real_schema_fields():
    if not OPENAPI_SUBSET.exists():
        return  # schema copy not present in this checkout; nothing to check against
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
    assert "strategy_text" in result["result"]["error"]
    assert result["latency_ms"] is not None


def test_invoke_errors_on_wrong_type_for_strategy_text():
    """Malformed input: strategy_text present but not a string."""
    ryo = FixtureRyoClient(load_envelope_fixtures())
    result = invoke({"strategy_text": 12345}, llm=DEMO_FIXTURE_LLM, ryo=ryo)
    assert result["status"] == "error"
    assert result["name"] == "compile_strategy"


def test_invoke_errors_on_wrong_type_for_user_declared():
    """Malformed input: user_declared present but not an object.

    Caught explicitly, not left to Python's duck-typing: a string's `in`
    operator does substring matching, so a garbage string could otherwise
    coincidentally "match" a metric name instead of failing loudly.
    """
    ryo = FixtureRyoClient(load_envelope_fixtures())
    result = invoke(
        {"strategy_text": "Buy SOL when SOL momentum is above 50.", "user_declared": "not-a-dict"},
        llm=DEMO_FIXTURE_LLM,
        ryo=ryo,
    )
    assert result["status"] == "error"
    assert "user_declared" in result["result"]["error"]


def test_invoke_on_unsupported_condition_reports_unresolved_not_a_crash():
    """Unsupported evidence (no RYO tool covers it) must come back as a
    clean, predictable success-with-UNKNOWN receipt, not an exception.
    """
    ryo = FixtureRyoClient(load_envelope_fixtures())
    result = invoke(
        {"strategy_text": "Never trade if the required safety check fails.", "user_declared": {}},
        llm=DEMO_FIXTURE_LLM,
        ryo=ryo,
    )
    assert result["status"] == "success"
    assert result["result"]["decision"] == "UNKNOWN"
    assert result["result"]["unresolved_rule_ids"] == ["rule_1"]


def test_invoke_error_shape_is_stable_across_failure_modes():
    """Every error path returns the same top-level keys, so a caller can
    branch on `status` without knowing which specific thing went wrong.
    """
    ryo = FixtureRyoClient(load_envelope_fixtures())
    missing = invoke({}, llm=DEMO_FIXTURE_LLM, ryo=ryo)
    bad_type = invoke({"strategy_text": 123}, llm=DEMO_FIXTURE_LLM, ryo=ryo)
    for result in (missing, bad_type):
        assert result["status"] == "error"
        assert set(result.keys()) <= {"name", "status", "result", "latency_ms", "xp", "guard_decision"}
        assert "error" in result["result"]
