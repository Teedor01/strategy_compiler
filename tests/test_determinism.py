from strategy_compiler.decide import decide
from strategy_compiler.fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from strategy_compiler.receipt import receipt_to_dict
from strategy_compiler.ryo_client import FixtureRyoClient

STRATEGY = "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 20% of the portfolio."
N_RUNS = 5


def _strip_timestamps(receipt_dict: dict) -> dict:
    stripped = dict(receipt_dict)
    stripped.pop("compiled_at", None)
    stripped.pop("generated_at", None)
    return stripped


def test_identical_inputs_produce_byte_identical_receipts_except_timestamps():
    receipts = [
        receipt_to_dict(
            decide(
                STRATEGY,
                llm=DEMO_FIXTURE_LLM,
                ryo=FixtureRyoClient(load_envelope_fixtures()),
                user_declared={"allocation_pct": 0.15},
            )
        )
        for _ in range(N_RUNS)
    ]

    first_stripped = _strip_timestamps(receipts[0])
    for other in receipts[1:]:
        assert _strip_timestamps(other) == first_stripped

    trace_ids = {r["trace_id"] for r in receipts}
    assert len(trace_ids) == 1

    decisions = {r["decision"] for r in receipts}
    assert decisions == {"ALLOW"}

    blocking = {tuple(r["blocking_rule_ids"]) for r in receipts}
    assert blocking == {()}


    compiled_ats = {r["compiled_at"] for r in receipts}
    generated_ats = {r["generated_at"] for r in receipts}
    assert len(compiled_ats) >= 1 and len(generated_ats) >= 1
