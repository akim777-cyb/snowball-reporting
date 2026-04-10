"""
Fund-level narrative generation using the Claude API.

Each fund gets one narrative per quarter. The narrative is written once,
approved by Andres via the Flask UI, and then merged into every
investor's PDF letter for that fund.
"""
import os
from pathlib import Path
from anthropic import Anthropic
from .schemas import FundPerformance, QuarterInputs, FundVehicle


FUND_DISPLAY_NAMES = {
    "GP1": "Snowball GP Fund #1",
    "GP2": "Snowball GP Fund #2",
    "CAD_FEEDER": "Snowball Canadian Feeder Fund",
}

# Per-fund prompt strategies — different voice/angle per vehicle
FUND_ANGLES = {
    "GP1": (
        "This is GP Fund #1 — fully deployed, 14 assets, operating phase. "
        "Focus on operational execution, lease-up progress, mark-to-market "
        "rent capture on rollover, solar program contribution, and asset-level "
        "value creation. Mention specific assets by name."
    ),
    "GP2": (
        "This is GP Fund #2 — actively raising, $25M target. "
        "Focus on the capital deployment story: pipeline, closings under way, "
        "conviction in the value-add industrial thesis for the Tri-State, and "
        "what investors should expect as the fund deploys."
    ),
    "CAD_FEEDER": (
        "This is the Canadian Feeder Fund. "
        "Focus on cross-border execution, FX context, alignment with the "
        "underlying GP fund strategy, and the unique opportunity for "
        "Canadian investors in Tri-State industrial real estate. Acknowledge "
        "the withholding treatment briefly and professionally."
    ),
}


def _build_prompt(
    fund: FundPerformance,
    highlights: list[str],
    reporting_period: str,
) -> str:
    fund_name = FUND_DISPLAY_NAMES[fund.fund_vehicle]
    angle = FUND_ANGLES[fund.fund_vehicle]

    assets_str = "\n".join(
        f"  - {a.asset_name} ({a.state}): {a.sf:,} SF, "
        f"{a.occupancy_pct:.0f}% occupied, ${a.in_place_noi:,.0f} NOI, "
        f"{a.yoy_noi_change_pct:+.1f}% YoY"
        for a in fund.assets
    )

    highlights_str = "\n".join(f"  - {h}" for h in highlights)

    return f"""You are writing a quarterly letter narrative from Snowball Developments to limited partners in {fund_name}.

Reporting period: {reporting_period}

Fund angle:
{angle}

Fund performance this quarter:
- Quarter-end NAV: ${fund.quarter_end_nav:,.0f}
- Quarterly distribution per unit: ${fund.quarterly_distribution_per_unit:.2f}
- YTD Net IRR: {fund.ytd_net_irr:.1f}%
- ITD Net IRR: {fund.itd_net_irr:.1f}%
- ITD Equity Multiple: {fund.itd_equity_multiple:.2f}x
- Fund unfunded commitment: ${fund.fund_unfunded_commitment:,.0f}

Asset-level performance:
{assets_str}

Quarter highlights from the portfolio management team:
{highlights_str}

Voice and style:
- Institutional, confident, plain-spoken
- Match the tone of a seasoned real estate operator, not a marketing writer
- Reference specific assets and specific metrics — no generic language
- DO NOT invent any figures not provided above
- 250-400 words
- Write as a continuous narrative, not bullet points
- Open with the quarter's headline, not with "We are pleased to announce"
- Close with a forward-looking note on the next quarter

Write only the letter body. No greeting, no signature, no subject line. Begin with the first sentence of the narrative."""


def generate_narrative(
    fund: FundPerformance,
    highlights: list[str],
    reporting_period: str,
) -> str:
    """
    Call the Claude API to generate a fund-level narrative.
    Requires ANTHROPIC_API_KEY in environment.
    """
    client = Anthropic()
    prompt = _build_prompt(fund, highlights, reporting_period)

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text blocks
    return "".join(
        block.text for block in message.content if hasattr(block, "text")
    ).strip()


def save_narrative(narrative: str, fund_vehicle: FundVehicle, quarter: str, dir_path: Path):
    """Save an approved narrative to disk."""
    dir_path.mkdir(parents=True, exist_ok=True)
    safe_quarter = quarter.replace(" ", "_")
    out = dir_path / f"{fund_vehicle}_{safe_quarter}.txt"
    out.write_text(narrative)
    return out


def load_narrative(fund_vehicle: FundVehicle, quarter: str, dir_path: Path) -> str:
    safe_quarter = quarter.replace(" ", "_")
    path = dir_path / f"{fund_vehicle}_{safe_quarter}.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"Narrative not yet approved for {fund_vehicle} {quarter}. "
            f"Run the approval UI first."
        )
    return path.read_text()
