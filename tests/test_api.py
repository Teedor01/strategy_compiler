from fastapi.testclient import TestClient

from strategy_compiler.api import app

client = TestClient(app)


def test_index_serves_ui():
    res = client.get("/")
    assert res.status_code == 200
    assert b"Strategy Compiler" in res.content


def test_skill_endpoint():
    res = client.get("/api/skill")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "compile_strategy"


def test_decide_endpoint_returns_receipt():
    res = client.post(
        "/api/decide",
        json={
            "strategy_text": "Buy SOL when SOL momentum is above 50.",
            "allocation_pct": 0.15,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] in {"ALLOW", "BLOCK", "UNKNOWN"}
    assert body["rules"][0]["metric"] == "momentum_state"
