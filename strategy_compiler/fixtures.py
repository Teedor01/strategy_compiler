from __future__ import annotations

from .envelope import parse_envelope
from .llm import FixtureLLM


CANNED_TRANSLATIONS = {
    "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 20% of the portfolio.": [
        {
            "raw_text": "momentum is positive",
            "asset": "SOL",
            "metric": "momentum_state",
            "operator": "==",
            "value": "positive",
            "ambiguity_note": None,
        },
        {
            "raw_text": "BTC isn't bearish",
            "asset": "BTC",
            "metric": "market_regime",
            "operator": "!=",
            "value": "risk_off",
            "ambiguity_note": None,
        },
        {
            "raw_text": "SOL stays below 20% of the portfolio",
            "asset": "SOL",
            "metric": "allocation_pct",
            "operator": "<",
            "value": 0.20,
            "ambiguity_note": None,
        },
    ],
    "Buy SOL when momentum is positive, BTC isn't bearish, and SOL stays below 10% of the portfolio.": [
        {
            "raw_text": "momentum is positive",
            "asset": "SOL",
            "metric": "momentum_state",
            "operator": "==",
            "value": "positive",
            "ambiguity_note": None,
        },
        {
            "raw_text": "BTC isn't bearish",
            "asset": "BTC",
            "metric": "market_regime",
            "operator": "!=",
            "value": "risk_off",
            "ambiguity_note": None,
        },
        {
            "raw_text": "SOL stays below 10% of the portfolio",
            "asset": "SOL",
            "metric": "allocation_pct",
            "operator": "<",
            "value": 0.10,
            "ambiguity_note": None,
        },
    ],
    # --- ugly real-world sentences from the project brief's own test list ---
    "Buy SOL only when momentum is strong.": [
        {
            "raw_text": "momentum is strong",
            "asset": "SOL",
            "metric": "momentum_state",
            "operator": None,
            "value": None,
            "ambiguity_note": "'strong' has no defined threshold; the human did not state one",
        }
    ],
    "Buy SOL when momentum is strong.": [
        {
            "raw_text": "momentum is strong",
            "asset": "SOL",
            "metric": "momentum_state",
            "operator": None,
            "value": None,
            "ambiguity_note": "'strong' has no defined threshold; the human did not state one",
        }
    ],
    "If BTC is looking bad, just leave the alt alone.": [
        {
            "raw_text": "If BTC is looking bad, just leave the alt alone",
            "asset": None,
            "metric": "market_regime",
            "operator": None,
            "value": None,
            "ambiguity_note": "'looking bad' does not map to a defined RYO market_regime "
            "value (risk_on|risk_off|rotation|chop); the human did not specify which",
        }
    ],
    "Don't put too much of the pot into one coin.": [
        {
            "raw_text": "Don't put too much of the pot into one coin",
            "asset": None,
            "metric": "allocation_pct",
            "operator": None,
            "value": None,
            "ambiguity_note": "'too much' has no defined percentage; the human did not state one",
        }
    ],
    "Never trade if the required safety check fails.": [
        {
            "raw_text": "the required safety check fails",
            "asset": None,
            "metric": "safety_check",
            "operator": "==",
            "value": "fail",
            "ambiguity_note": None,
        }
    ],
    "Buy SOL when momentum is above 60 and SOL momentum is below 40.": [
        {
            "raw_text": "momentum is above 60",
            "asset": "SOL",
            "metric": "momentum_state",
            "operator": ">",
            "value": 60,
            "ambiguity_note": None,
        },
        {
            "raw_text": "SOL momentum is below 40",
            "asset": "SOL",
            "metric": "momentum_state",
            "operator": "<",
            "value": 40,
            "ambiguity_note": None,
        },
    ],
    "Only buy SOL if it requires evidence RYO cannot provide, like wallet cluster risk.": [
        {
            "raw_text": "wallet cluster risk",
            "asset": "SOL",
            "metric": "wallet_cluster_risk",
            "operator": "==",
            "value": "low",
            "ambiguity_note": None,
        }
    ],
    "Buy SOL when SOL momentum is above 50.": [
        {
            "raw_text": "SOL momentum is above 50",
            "asset": "SOL",
            "metric": "momentum_state",
            "operator": ">",
            "value": 50,
            "ambiguity_note": None,
        }
    ],
    # --- multiple blocking rules in one strategy ---
    "Buy SOL only if momentum is above 90 and SOL stays below 5% of the portfolio.": [
        {
            "raw_text": "momentum is above 90",
            "asset": "SOL",
            "metric": "momentum_state",
            "operator": ">",
            "value": 90,
            "ambiguity_note": None,
        },
        {
            "raw_text": "SOL stays below 5% of the portfolio",
            "asset": "SOL",
            "metric": "allocation_pct",
            "operator": "<",
            "value": 0.05,
            "ambiguity_note": None,
        },
    ],
}

DEMO_FIXTURE_LLM = FixtureLLM(CANNED_TRANSLATIONS)




_MARKET_OVERVIEW_RISK_ON = {
    "schema_version": "1.0",
    "tool": "market_overview",
    "status": "ok",
    "data_mode": "simulated",
    "as_of": "2026-09-20T00:00:00Z",
    "request": {},
    "data": {"regime": "risk_on", "sentiment": {"fear_greed_index": 74.0, "label": "greed"}},
    "summary": {"headline": "[FIXTURE] Market regime: risk_on", "key_points": []},
    "availability": {"regime": "available", "sentiment": "available"},
    "warnings": [
        (
            "This is a hand-built local fixture, not a live RYO response. "
            "data_mode is deliberately 'simulated'."
        )
    ],
}

_ANALYZE_TOKEN_SOL_STRONG = {
    "schema_version": "1.0",
    "tool": "analyze_token",
    "status": "ok",
    "data_mode": "simulated",
    "as_of": "2026-09-20T00:00:00Z",
    "request": {"symbol": "SOL"},
    "data": {
        "asset": {"symbol": "SOL", "name": "Solana", "rank": 7},
        "market": {"price_usd": 111.76},
        "performance": {"change_24h_pct": 1.32},
        "technical_analysis": {"trend": "up", "rsi_14": 62.4, "atr_14_pct": 3.1},
    },
    "summary": {"headline": "[FIXTURE] SOL RSI(14) 62.4", "key_points": []},
    "availability": {"technical_analysis": "available", "market": "available", "asset": "available"},
    "warnings": [
        (
            "This is a hand-built local fixture, not a live RYO response. "
            "data_mode is deliberately 'simulated'."
        )
    ],
}


def load_envelope_fixtures() -> dict[str, object]:
    return {
        "market_overview": parse_envelope(_MARKET_OVERVIEW_RISK_ON),
        "analyze_token": parse_envelope(_ANALYZE_TOKEN_SOL_STRONG),
    }
