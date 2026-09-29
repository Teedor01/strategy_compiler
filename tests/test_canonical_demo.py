import io
from contextlib import redirect_stdout

from strategy_compiler.demo import PROVENANCE_LABEL, run_canonical_demo


def test_canonical_demo_runs_clean_and_proves_its_claims():
    buf = io.StringIO()
    with redirect_stdout(buf):
        run_canonical_demo()  
    output = buf.getvalue()

    assert "TRADE ALLOWED" in output
    assert "TRADE BLOCKED" in output
    assert "rule_3" in output
    assert "NEEDS_CLARIFICATION" in output
    assert "The system will not invent a threshold." in output
    assert "No hallucinated substitute." in output
    assert "identical." in output 
    assert "NOT REPRODUCIBLE" not in output


    assert PROVENANCE_LABEL in output
    assert "live RYO" not in output.replace("No live RYO", "")  # the one permitted negative mention
    assert "RECORDED FROM LIVE RYO DATA" not in output
