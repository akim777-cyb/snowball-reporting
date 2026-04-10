"""
Data ingestion layer.

PRODUCTION SWAP POINT: This module would be replaced with a Juniper Square
API connector. The functions below would call JSQ endpoints for investor
accounts and performance data. The Pydantic schemas in schemas.py stay
identical — only the data source changes.
"""
from pathlib import Path
import pandas as pd
from typing import List
from .schemas import (
    Investor,
    FundPerformance,
    AssetPerformance,
    QuarterInputs,
    FundVehicle,
)


FUND_TABS = {
    "GP1": "GP_Fund_1",
    "GP2": "GP_Fund_2",
    "CAD_FEEDER": "CAD_Feeder",
}


def load_investors(path: Path) -> List[Investor]:
    """
    Load investor roster from Excel.
    Auto-detects the header row so Juniper Square-style exports with
    title/metadata rows at the top load correctly alongside simple rosters.

    Production: replace with `jsq_client.list_investors()`.
    """
    # Scan the first 15 rows for the header row (one containing "Investor ID")
    raw = pd.read_excel(path, header=None, nrows=15)
    header_row = 0
    for idx, row in raw.iterrows():
        if any("Investor ID" == str(cell).strip() for cell in row if pd.notna(cell)):
            header_row = idx
            break

    df = pd.read_excel(path, header=header_row)
    # Drop any fully-empty rows
    df = df.dropna(how="all")

    investors = []
    for _, row in df.iterrows():
        # Skip rows where Investor ID is missing (footer rows, etc.)
        if pd.isna(row.get("Investor ID")):
            continue
        investors.append(
            Investor(
                investor_id=str(row["Investor ID"]),
                investor_name=str(row["Investor Name"]),
                fund_vehicle=row["Fund Vehicle"],
                investor_type=row["Investor Type"],
                country=row["Country"],
                commitment=float(row["Commitment"]),
                total_contributed=float(row["Total Contributed"]),
                total_distributed=float(row["Total Distributed"]),
                ownership_pct=float(row["Ownership %"]),
                email=str(row["Email"]),
                mailing_address=str(row["Mailing Address"]),
            )
        )
    return investors


def load_fund_performance(path: Path) -> dict[FundVehicle, FundPerformance]:
    """
    Load fund-level performance from Excel.
    Production: replace with `jsq_client.get_fund_performance(fund_id, quarter)`.
    """
    xls = pd.ExcelFile(path)
    funds: dict[FundVehicle, FundPerformance] = {}

    for fund_code, tab_name in FUND_TABS.items():
        # Read the summary block (top of sheet, key-value format)
        summary = pd.read_excel(xls, sheet_name=tab_name, nrows=7, header=None)
        summary_dict = dict(zip(summary[0], summary[1]))

        # Read the asset table (starts below the summary block)
        assets_df = pd.read_excel(xls, sheet_name=tab_name, skiprows=9)
        assets = []
        for _, row in assets_df.iterrows():
            if pd.isna(row.get("Asset Name")):
                continue
            assets.append(
                AssetPerformance(
                    asset_name=str(row["Asset Name"]),
                    state=str(row["State"]),
                    sf=int(row["SF"]),
                    occupancy_pct=float(row["Occupancy %"]),
                    in_place_noi=float(row["In-Place NOI"]),
                    yoy_noi_change_pct=float(row["YoY NOI Change %"]),
                    valuation_mark=float(row["Valuation Mark"]),
                )
            )

        funds[fund_code] = FundPerformance(
            fund_vehicle=fund_code,
            quarter_end_nav=float(summary_dict["Quarter-End NAV"]),
            quarterly_distribution_per_unit=float(
                summary_dict["Quarterly Distribution per Unit"]
            ),
            ytd_net_irr=float(summary_dict["YTD Net IRR"]),
            itd_net_irr=float(summary_dict["ITD Net IRR"]),
            ytd_equity_multiple=float(summary_dict["YTD Equity Multiple"]),
            itd_equity_multiple=float(summary_dict["ITD Equity Multiple"]),
            fund_unfunded_commitment=float(
                summary_dict["Fund Unfunded Commitment"]
            ),
            assets=assets,
        )

    return funds


def load_quarter_inputs(path: Path) -> QuarterInputs:
    """
    Load quarter-specific inputs (FX, withholding, highlights).
    Production: FX rate hits an API; highlights come from a web form
    that Andres fills out each quarter.
    """
    df = pd.read_excel(path, sheet_name="Config", header=None)
    config = dict(zip(df[0], df[1]))

    highlights_df = pd.read_excel(path, sheet_name="Highlights")
    highlights_gp1 = [
        str(v) for v in highlights_df["GP1"].dropna().tolist()
    ]
    highlights_gp2 = [
        str(v) for v in highlights_df["GP2"].dropna().tolist()
    ]
    highlights_cad = [
        str(v) for v in highlights_df["CAD_FEEDER"].dropna().tolist()
    ]

    return QuarterInputs(
        reporting_period=str(config["Reporting Period"]),
        fx_rate_usd_cad=float(config["FX Rate USD/CAD"]),
        cad_withholding_rate=float(config["CAD Withholding Rate"]),
        highlights_gp1=highlights_gp1,
        highlights_gp2=highlights_gp2,
        highlights_cad=highlights_cad,
    )


def validate_reconciliation(
    investors: List[Investor],
    funds: dict[FundVehicle, FundPerformance],
) -> List[str]:
    """
    Sanity checks that would catch data entry errors before any
    investor-facing document is generated.
    """
    warnings = []
    for fund_code in funds.keys():
        fund_investors = [i for i in investors if i.fund_vehicle == fund_code]
        total_ownership = sum(i.ownership_pct for i in fund_investors)
        if abs(total_ownership - 100.0) > 0.5:
            warnings.append(
                f"{fund_code}: ownership sums to {total_ownership:.2f}%, expected 100.00%"
            )
    return warnings
