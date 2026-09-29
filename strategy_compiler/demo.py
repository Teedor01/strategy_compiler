from __future__ import annotations

from .decide import decide
from .fixtures import DEMO_FIXTURE_LLM, load_envelope_fixtures
from .receipt import SIMULATED_EVIDENCE_LABEL, receipt_to_dict
from .ryo_client import FixtureRyoClient

RULE = "─" * 70


PROVENANCE_LABEL = SIMULATED_EVIDENCE_LABEL

SCENARIO_A = "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 20% of the portfolio."
SCENARIO_B = "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 10% of the portfolio."
AMBIGUOUS_STRATEGY = "Buy SOL when momentum is strong."
UNSUPPORTED_STRATEGY = "Never trade if the required safety check fails."


def _print_flow_stage(label: str) -> None:
    print(f"\n{label}")
    print("        ↓")


def _print_receipt_stages(strategy_text: str, allocation_pct: float) -> dict:
    print(RULE)
    print("NATURAL-LANGUAGE STRATEGY")
    print(f'  "{strategy_text}"')
    print("        ↓")

    ryo = FixtureRyoClient(load_envelope_fixtures())
    receipt = decide(strategy_text, llm=DEMO_FIXTURE_LLM, ryo=ryo, user_declared={"allocation_pct": allocation_pct})
    body = receipt_to_dict(receipt)

    print("COMPILED RULES")
    for rule in body["rules"]:
        print(f"  [{rule['id']}] {rule['raw_text']!r} -> {rule['metric']} {rule['operator']} {rule['value']} ({rule['status']})")
    print("        ↓")

    print(f"RYO EVIDENCE   [{PROVENANCE_LABEL}]")
    for r in body["rule_results"]:
        ev = r["evidence"]
        if ev is None:
            print(f"  [{r['rule_id']}] no evidence resolved ({r['status']})")
            continue
        print(f"  [{r['rule_id']}] {ev['metric']} = {ev['value']!r}  (source: {ev['provenance']})")
    print("        ↓")

    print("RULE-BY-RULE EVALUATION")
    for r in body["rule_results"]:
        print(f"  [{r['rule_id']}] {r['status']:8s} — {r['explanation']}")
    print("        ↓")

    decision_label = {"ALLOW": "TRADE ALLOWED", "BLOCK": "TRADE BLOCKED", "UNKNOWN": "DECISION: UNKNOWN"}[body["decision"]]
    print(decision_label)
    if body["blocking_rule_ids"]:
        print(f"  blocking rule: {', '.join(body['blocking_rule_ids'])}")
    print(f"  trace_id: {body['trace_id']}")
    print(RULE)
    return body


def run_canonical_demo() -> None:
    print(RULE)
    print("CANONICAL DEMO — Strategy Compiler")
    print(f"All RYO evidence below is [{PROVENANCE_LABEL}].")
    print("No live RYO or Anthropic credential was used to produce this output.")
    print(RULE)

    print("\n\n=== SCENARIO A: 20% allocation cap ===")
    receipt_a = _print_receipt_stages(SCENARIO_A, allocation_pct=0.15)
    assert receipt_a["decision"] == "ALLOW"

    print("\n\n=== SCENARIO B: change ONLY '20%' -> '10%'. SAME evidence. ===")
    receipt_b = _print_receipt_stages(SCENARIO_B, allocation_pct=0.15)
    assert receipt_b["decision"] == "BLOCK"

    print("\nSAME EVIDENCE")
    print("        +")
    print("DIFFERENT HUMAN POLICY")
    print("        ↓")
    print("TRADE BLOCKED")
    print(f"        ↓\n{', '.join(receipt_b['blocking_rule_ids'])}")

    print("\n\n=== FAILURE STORY 1: undefined threshold ===")
    ryo = FixtureRyoClient(load_envelope_fixtures())
    receipt_c = receipt_to_dict(decide(AMBIGUOUS_STRATEGY, llm=DEMO_FIXTURE_LLM, ryo=ryo, user_declared={}))
    print(f'  "{AMBIGUOUS_STRATEGY}"')
    print(f"  -> {receipt_c['rules'][0]['status']}")
    print(f"  \"{receipt_c['rules'][0]['problem']}\"")
    print("  The system will not invent a threshold.")
    assert receipt_c["decision"] == "UNKNOWN"
    assert receipt_c["rules"][0]["status"] == "NEEDS_CLARIFICATION"

    print("\n\n=== FAILURE STORY 2: unsupported evidence ===")
    ryo = FixtureRyoClient(load_envelope_fixtures())
    receipt_d = receipt_to_dict(decide(UNSUPPORTED_STRATEGY, llm=DEMO_FIXTURE_LLM, ryo=ryo, user_declared={}))
    print(f'  "{UNSUPPORTED_STRATEGY}"')
    print(f"  -> {receipt_d['decision']}")
    print("  Required evidence unavailable from RYO.")
    print("  No hallucinated substitute.")
    assert receipt_d["decision"] == "UNKNOWN"
    assert receipt_d["rules"][0]["status"] == "UNSUPPORTED"

    print("\n\n=== REPRODUCIBILITY: Scenario A run 3 more times, identical fixture evidence ===")
    trace_ids = {receipt_a["trace_id"]}
    for _ in range(3):
        ryo = FixtureRyoClient(load_envelope_fixtures())
        r = receipt_to_dict(decide(SCENARIO_A, llm=DEMO_FIXTURE_LLM, ryo=ryo, user_declared={"allocation_pct": 0.15}))
        trace_ids.add(r["trace_id"])
    if len(trace_ids) == 1:
        print(f"  4/4 runs produced trace_id {trace_ids.pop()} — identical.")
    else:
        print(f"  NOT REPRODUCIBLE: {len(trace_ids)} distinct trace_ids produced: {trace_ids}")
        raise SystemExit(1)

    print(RULE)
    print("End of canonical demo.")
    print(RULE)


if __name__ == "__main__":
    run_canonical_demo()
