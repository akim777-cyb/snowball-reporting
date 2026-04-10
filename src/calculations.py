"""
Per-investor capital account rollforward calculations.

Logic: allocate fund-level performance to each investor by ownership %,
compute period activity, and produce the CapitalAccountStatement object
that feeds the PDF generator.
"""
from typing import List
from .schemas import (
    Investor,
    FundPerformance,
    CapitalAccountStatement,
    QuarterInputs,
)


def compute_statements(
    investors: List[Investor],
    funds: dict,
    quarter: QuarterInputs,
) -> List[CapitalAccountStatement]:
    """
    For each investor, compute their capital account statement for the quarter.

    Simplified model for the demo: we treat all prior contributions and
    distributions as ITD figures, and split the quarter into mock period
    activity using a 25% allocation rule. In production this would read
    actual period transactions from Juniper Square.
    """
    statements = []

    for investor in investors:
        fund = funds[investor.fund_vehicle]
        ownership_decimal = investor.ownership_pct / 100.0

        # Investor's allocated share of fund NAV
        ending_balance = fund.quarter_end_nav * ownership_decimal

        # Period activity (mock split for demo: 20% of ITD hits this quarter)
        period_contributions = investor.total_contributed * 0.20
        period_distributions = investor.total_distributed * 0.25

        # Allocated net income — derived from fund ITD IRR on a quarterly basis
        # Applied to prior-period ending balance (ending - period activity)
        pre_activity_balance = (
            ending_balance - period_contributions + period_distributions
        )
        quarterly_rate = fund.itd_net_irr / 100.0 / 4.0
        allocated_net_income = pre_activity_balance * quarterly_rate

        # Beginning balance backs into the rollforward
        beginning_balance = (
            ending_balance
            - period_contributions
            + period_distributions
            - allocated_net_income
        )

        # Committed but uncalled = commitment - total contributed
        committed_uncalled = max(
            0.0, investor.commitment - investor.total_contributed
        )
        # Remaining unfunded commitment mirrors this for the demo
        remaining_unfunded = committed_uncalled

        stmt = CapitalAccountStatement(
            investor=investor,
            fund_performance=fund,
            beginning_capital_balance=beginning_balance,
            period_contributions=period_contributions,
            period_distributions=period_distributions,
            allocated_net_income=allocated_net_income,
            ending_capital_balance=ending_balance,
            itd_net_irr=fund.itd_net_irr,
            itd_equity_multiple=fund.itd_equity_multiple,
            committed_uncalled=committed_uncalled,
            remaining_unfunded_commitment=remaining_unfunded,
        )

        # Canadian feeder — apply FX and withholding
        if investor.fund_vehicle == "CAD_FEEDER":
            stmt.fx_rate_usd_cad = quarter.fx_rate_usd_cad
            stmt.cad_withholding_rate = quarter.cad_withholding_rate
            stmt.ending_balance_cad = ending_balance * quarter.fx_rate_usd_cad
            stmt.withholding_amount_cad = (
                period_distributions
                * quarter.fx_rate_usd_cad
                * quarter.cad_withholding_rate
            )

        statements.append(stmt)

    return statements
