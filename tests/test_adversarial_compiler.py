from strategy_compiler.compiler import compile_strategy
from strategy_compiler.llm import FixtureLLM
from strategy_compiler.schema import RuleStatus

ADVERSARIAL_TRANSLATIONS = {
    "Buy SOL when it looks cheap.": [
        {
            "raw_text": "it looks cheap",
            "asset": "SOL",
            "metric": "price_usd",
            "operator": None,
            "value": None,
            "ambiguity_note": "'cheap' has no defined price threshold",
        }
    ],
    "Only buy if the upside is worth the risk.": [
        {
            "raw_text": "the upside is worth the risk",
            "asset": None,
            "metric": None,
            "operator": None,
            "value": None,
            "ambiguity_note": "'upside worth the risk' is a subjective risk/reward "
            "judgment with no single measurable quantity RYO or this project defines",
        }
    ],
    "Don't chase SOL after a huge pump.": [
        {
            "raw_text": "after a huge pump",
            "asset": "SOL",
            "metric": "change_24h_pct",
            "operator": None,
            "value": None,
            "ambiguity_note": "'huge pump' has no defined percentage threshold",
        }
    ],
    "Buy SOL when sentiment is good.": [
        {
            "raw_text": "sentiment is good",
            "asset": None,
            "metric": "fear_greed_index",
            "operator": None,
            "value": None,
            "ambiguity_note": "'good' sentiment has no defined Fear & Greed threshold",
        }
    ],
    "If BTC is weak, don't touch alts.": [
        {
            "raw_text": "If BTC is weak, don't touch alts",
            "asset": "BTC",
            "metric": "market_regime",
            "operator": None,
            "value": None,
            "ambiguity_note": "'weak' does not map to a defined RYO market_regime "
            "value (risk_on|risk_off|rotation|chop)",
        }
    ],
    "Keep the portfolio diversified.": [
        {
            "raw_text": "Keep the portfolio diversified",
            "asset": None,
            "metric": "portfolio_diversification",
            "operator": ">=",
            "value": 5,
            "ambiguity_note": None,
        }
    ],
}


def _compile(text):
    return compile_strategy(text, FixtureLLM(ADVERSARIAL_TRANSLATIONS))


def test_looks_cheap_needs_clarification_not_invented_price():
    strategy = _compile("Buy SOL when it looks cheap.")
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
    assert strategy.rules[0].value is None  # no price was guessed


def test_upside_worth_the_risk_needs_clarification():
    strategy = _compile("Only buy if the upside is worth the risk.")
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
    assert strategy.rules[0].metric is None


def test_huge_pump_needs_clarification_not_invented_percentage():
    strategy = _compile("Don't chase SOL after a huge pump.")
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
    assert strategy.rules[0].value is None


def test_sentiment_is_good_needs_clarification_not_invented_threshold():
    strategy = _compile("Buy SOL when sentiment is good.")
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
    assert strategy.rules[0].value is None


def test_btc_is_weak_needs_clarification_not_invented_regime():
    strategy = _compile("If BTC is weak, don't touch alts.")
    assert strategy.rules[0].status is RuleStatus.NEEDS_CLARIFICATION
    assert strategy.rules[0].value is None


def test_keep_portfolio_diversified_is_unsupported_not_clarification():
    """Distinguishes UNSUPPORTED from NEEDS_CLARIFICATION: this rule has a
    concrete stated threshold (>= 5 assets), so it isn't ambiguous -- the
    problem is that no evidence source (RYO tool or user-declared field)
    measures cross-portfolio diversification at all.
    """
    strategy = _compile("Keep the portfolio diversified.")
    assert strategy.rules[0].status is RuleStatus.UNSUPPORTED
    assert strategy.rules[0].value == 5  # value WAS extracted -- it's support that's missing, not clarity


def test_all_six_adversarial_strategies_are_refused_not_silently_allowed():
    """Belt-and-suspenders: none of the six ever compiles to EXECUTABLE,
    and therefore none can ever silently resolve to ALLOW without a human
    supplying the missing definition.
    """
    for text in ADVERSARIAL_TRANSLATIONS:
        strategy = _compile(text)
        assert all(r.status is not RuleStatus.EXECUTABLE for r in strategy.rules), (
            f"{text!r} produced an EXECUTABLE rule from an undefined concept"
        )
