"""
Fund vehicle configuration — single source of truth for all fund metadata.

TO ADD A NEW FUND:
  1. Add a new entry to the FUNDS dictionary below
  2. That's it. No other files need to change.

The rest of the tool reads from this config at runtime:
  - schemas.py validates fund codes against FUNDS.keys()
  - web_ui.py builds fund performance objects from default_performance
  - narrative.py uses display_name and narrative_angle
  - pdf_generator.py uses display_name for letter headers
  - Demo highlights come from default_highlights
"""
from typing import Any


FUNDS: dict[str, dict[str, Any]] = {
    "GP1": {
        "display_name": "Snowball GP Fund #1",
        "currency": "USD",
        "is_feeder": False,
        "default_performance": {
            "quarter_end_nav": 168_500_000,
            "quarterly_distribution_per_unit": 0.45,
            "ytd_net_irr": 14.2,
            "itd_net_irr": 17.8,
            "ytd_equity_multiple": 1.08,
            "itd_equity_multiple": 1.42,
            "fund_unfunded_commitment": 0,
        },
        "narrative_angle": (
            "This is GP Fund #1 — fully deployed, 14 assets, operating phase. "
            "Focus on operational execution, lease-up progress, mark-to-market "
            "rent capture on rollover, solar program contribution, and asset-level "
            "value creation. Mention specific assets by name."
        ),
        "default_highlights": [
            "Portfolio occupancy reached 94% on a trailing basis, with ~350K SF of leases pending execution that will push occupancy toward 98% by Q2.",
            "Signed a new 10-year lease at South Windsor at $8.75 PSF NNN, a 42% mark-to-market premium over the prior in-place rent.",
            "Solar program expanded to 9 assets totaling 500K+ SF, now generating $245K in annual income at ~$0.50 PSF.",
            "Completed the South Windsor refinancing at $9.5M against a $9.0M total cost basis, returning equity to the partnership.",
            "Waterbury and Meriden executed 4 acres of outdoor storage leases, adding incremental cash flow with minimal capex.",
        ],
    },
    "GP2": {
        "display_name": "Snowball GP Fund #2",
        "currency": "USD",
        "is_feeder": False,
        "default_performance": {
            "quarter_end_nav": 10_250_000,
            "quarterly_distribution_per_unit": 0.0,
            "ytd_net_irr": 0.0,
            "itd_net_irr": 0.0,
            "ytd_equity_multiple": 1.0,
            "itd_equity_multiple": 1.0,
            "fund_unfunded_commitment": 15_000_000,
        },
        "narrative_angle": (
            "This is GP Fund #2 — actively raising, $25M target. "
            "Focus on the capital deployment story: pipeline, closings under way, "
            "conviction in the value-add industrial thesis for the Tri-State, and "
            "what investors should expect as the fund deploys."
        ),
        "default_highlights": [
            "Three initial assets acquired in Q1: Norwalk Industrial, Paterson Logistics, and North Haven, totaling 320K SF for approximately $30.4M.",
            "Pipeline includes 6 assets under contract representing 600K SF, with closings anticipated between February and April.",
            "Fund is on track to be fully deployed by the end of 2026.",
            "Value-add thesis unchanged: acquire land-heavy assets at below-replacement-cost basis in the Tri-State industrial market.",
        ],
    },
    "CAD_FEEDER": {
        "display_name": "Snowball Canadian Feeder Fund",
        "currency": "CAD",
        "is_feeder": True,
        "default_performance": {
            "quarter_end_nav": 5_200_000,
            "quarterly_distribution_per_unit": 0.42,
            "ytd_net_irr": 13.5,
            "itd_net_irr": 16.9,
            "ytd_equity_multiple": 1.07,
            "itd_equity_multiple": 1.38,
            "fund_unfunded_commitment": 0,
        },
        "narrative_angle": (
            "This is the Canadian Feeder Fund. "
            "Focus on cross-border execution, FX context, alignment with the "
            "underlying GP fund strategy, and the unique opportunity for "
            "Canadian investors in Tri-State industrial real estate. Acknowledge "
            "the withholding treatment briefly and professionally."
        ),
        "default_highlights": [
            "The Canadian Feeder participated pro rata in GP Fund #1's Q1 activity, including the South Windsor refinancing and solar program expansion.",
            "FX conditions remained stable through the quarter at approximately 1.365 USD/CAD.",
            "No changes to the Canadian non-resident withholding rate of 15% on distributions.",
            "Eastern Canada expansion under evaluation for potential future feeder vehicles.",
        ],
    },
}


def fund_codes() -> list[str]:
    """Return all configured fund vehicle codes."""
    return list(FUNDS.keys())


def display_name(code: str) -> str:
    return FUNDS[code]["display_name"]


def currency(code: str) -> str:
    return FUNDS[code]["currency"]


def is_feeder(code: str) -> bool:
    return FUNDS[code]["is_feeder"]


def default_performance(code: str) -> dict[str, Any]:
    return FUNDS[code]["default_performance"].copy()


def narrative_angle(code: str) -> str:
    return FUNDS[code]["narrative_angle"]


def default_highlights(code: str) -> list[str]:
    return list(FUNDS[code]["default_highlights"])


def all_display_names() -> dict[str, str]:
    """Map fund code -> display name for legacy callers."""
    return {code: data["display_name"] for code, data in FUNDS.items()}
