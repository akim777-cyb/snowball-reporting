"""
Pydantic schemas for investor reporting data.
These mirror the structure of Juniper Square CSV exports so the
ingestion layer can be swapped to a JSQ API connector in production.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from decimal import Decimal


FundVehicle = Literal["GP1", "GP2", "CAD_FEEDER"]
InvestorType = Literal["HNW", "Family Office", "Institutional"]
Country = Literal["US", "Canada"]


class Investor(BaseModel):
    """One row from investor_roster.xlsx"""
    investor_id: str
    investor_name: str
    fund_vehicle: FundVehicle
    investor_type: InvestorType
    country: Country
    commitment: float
    total_contributed: float
    total_distributed: float
    ownership_pct: float
    email: str
    mailing_address: str

    @field_validator("ownership_pct")
    @classmethod
    def validate_ownership(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError(f"ownership_pct must be between 0 and 100, got {v}")
        return v


class AssetPerformance(BaseModel):
    """One row in the asset-level performance table"""
    asset_name: str
    state: str
    sf: int
    occupancy_pct: float
    in_place_noi: float
    yoy_noi_change_pct: float
    valuation_mark: float


class FundPerformance(BaseModel):
    """One tab of fund_performance.xlsx"""
    fund_vehicle: FundVehicle
    quarter_end_nav: float
    quarterly_distribution_per_unit: float
    ytd_net_irr: float
    itd_net_irr: float
    ytd_equity_multiple: float
    itd_equity_multiple: float
    fund_unfunded_commitment: float
    assets: List[AssetPerformance]


class QuarterInputs(BaseModel):
    """Contents of quarter_inputs.xlsx"""
    reporting_period: str  # e.g. "Q1 2026"
    fx_rate_usd_cad: float
    cad_withholding_rate: float
    highlights_gp1: List[str]
    highlights_gp2: List[str]
    highlights_cad: List[str]


class CapitalAccountStatement(BaseModel):
    """Per-investor computed values for the PDF"""
    investor: Investor
    fund_performance: FundPerformance
    beginning_capital_balance: float
    period_contributions: float
    period_distributions: float
    allocated_net_income: float
    ending_capital_balance: float
    itd_net_irr: float
    itd_equity_multiple: float
    committed_uncalled: float
    remaining_unfunded_commitment: float
    # Canadian-only fields
    fx_rate_usd_cad: Optional[float] = None
    cad_withholding_rate: Optional[float] = None
    ending_balance_cad: Optional[float] = None
    withholding_amount_cad: Optional[float] = None
