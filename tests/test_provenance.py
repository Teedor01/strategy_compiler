from strategy_compiler.decide import decide
from strategy_compiler.fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from strategy_compiler.receipt import SIMULATED_EVIDENCE_LABEL, receipt_to_dict
from strategy_compiler.ryo_client import FixtureRyoClient


def test_fixture_run_flags_contains_simulated_evidence():
    receipt = decide(
        "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 20% of the portfolio.",
        llm=DEMO_FIXTURE_LLM,
        ryo=FixtureRyoClient(load_envelope_fixtures()),
        user_declared={"allocation_pct": 0.15},
    )
    body = receipt_to_dict(receipt)
    assert body["contains_simulated_evidence"] is True
    assert body["simulated_evidence_label"] == SIMULATED_EVIDENCE_LABEL
    assert "RECORDED FROM LIVE" not in body["simulated_evidence_label"]  
    ryo_backed = [rid for rid, prov in body["evidence_provenance"].items() if prov == "simulated"]
    assert len(ryo_backed) == 2 


def test_user_declared_evidence_is_never_labelled_simulated():
    receipt = decide(
        "Buy SOL when SOL momentum is above 50.",
        llm=DEMO_FIXTURE_LLM,
        ryo=FixtureRyoClient(load_envelope_fixtures()),
        user_declared={},
    )
    body = receipt_to_dict(receipt)
    assert list(body["evidence_provenance"].values()) == ["simulated"]


def test_unresolved_evidence_is_labelled_unresolved_not_silently_blank():
    receipt = decide(
        "Never trade if the required safety check fails.",
        llm=DEMO_FIXTURE_LLM,
        ryo=FixtureRyoClient(load_envelope_fixtures()),
        user_declared={},
    )
    body = receipt_to_dict(receipt)
    result = body["rule_results"][0]
    assert result["status"] == "SKIPPED"
    assert result["evidence"] is None
