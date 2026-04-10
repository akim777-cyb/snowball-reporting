"""
PDF generation for investor capital account statements.

Produces one branded PDF letter per investor, merging the approved
fund narrative with that investor's capital account calculation.

Brand color: #2596be (Snowball light blue)
"""
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)
from .schemas import CapitalAccountStatement


SNOWBALL_BLUE = HexColor("#2596be")
SNOWBALL_BLUE_LIGHT = HexColor("#d4ecf4")
DARK_GRAY = HexColor("#333333")
LIGHT_GRAY = HexColor("#f5f5f5")


def _money(value: float, currency: str = "$") -> str:
    if value < 0:
        return f"({currency}{abs(value):,.2f})"
    return f"{currency}{value:,.2f}"


def _pct(value: float) -> str:
    return f"{value:.2f}%"


def _multiple(value: float) -> str:
    return f"{value:.2f}x"


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="LetterheadBrand",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=SNOWBALL_BLUE,
        spaceAfter=2,
        leading=26,
    ))
    styles.add(ParagraphStyle(
        name="LetterheadSub",
        fontName="Helvetica",
        fontSize=9,
        textColor=DARK_GRAY,
        spaceAfter=0,
        leading=11,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=SNOWBALL_BLUE,
        spaceBefore=14,
        spaceAfter=8,
        leading=14,
    ))
    styles.add(ParagraphStyle(
        name="BodyJustified",
        fontName="Times-Roman",
        fontSize=10.5,
        textColor=DARK_GRAY,
        alignment=TA_JUSTIFY,
        leading=14,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="InvestorBlock",
        fontName="Times-Roman",
        fontSize=10,
        textColor=DARK_GRAY,
        leading=13,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Footer",
        fontName="Helvetica",
        fontSize=8,
        textColor=HexColor("#666666"),
        alignment=TA_CENTER,
        leading=10,
    ))
    styles.add(ParagraphStyle(
        name="Disclosure",
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        textColor=DARK_GRAY,
        leading=11,
        spaceAfter=6,
    ))
    return styles


def _letterhead(styles):
    elements = []
    elements.append(Paragraph("SNOWBALL DEVELOPMENTS", styles["LetterheadBrand"]))
    elements.append(Paragraph(
        "Value-Add Industrial Real Estate &nbsp;&bull;&nbsp; Brooklyn, NY",
        styles["LetterheadSub"]
    ))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(
        width="100%", thickness=2, color=SNOWBALL_BLUE, spaceAfter=10
    ))
    return elements


def _investor_header(stmt: CapitalAccountStatement, styles, reporting_period: str):
    inv = stmt.investor
    today = datetime.now().strftime("%B %d, %Y")
    elements = []
    # Date right, investor left, via table
    left = Paragraph(
        f"<b>{inv.investor_name}</b><br/>"
        f"{inv.mailing_address.replace(chr(10), '<br/>')}",
        styles["InvestorBlock"],
    )
    right = Paragraph(
        f"<b>{reporting_period}</b><br/>{today}",
        ParagraphStyle(
            "DateRight",
            parent=styles["InvestorBlock"],
            alignment=2,  # right
        ),
    )
    t = Table([[left, right]], colWidths=[4.0 * inch, 2.5 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))

    fund_display = {
        "GP1": "Snowball GP Fund #1",
        "GP2": "Snowball GP Fund #2",
        "CAD_FEEDER": "Snowball Canadian Feeder Fund",
    }[inv.fund_vehicle]
    elements.append(Paragraph(
        f"Re: {fund_display} — Quarterly Capital Account Statement",
        ParagraphStyle(
            "Subject",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=DARK_GRAY,
            spaceAfter=10,
        ),
    ))
    # Entity vs individual greeting
    entity_markers = ("LLC", "LP", "Inc.", "Inc", "Trust", "Partners",
                      "Foundation", "Holdings", "Capital", "Fund", "Endowment",
                      "Corp", "Ltd", "Company")
    is_entity = any(m in inv.investor_name for m in entity_markers)
    if is_entity:
        greeting = f"Dear {inv.investor_name},"
    else:
        greeting = f"Dear {inv.investor_name.split()[0]},"
    elements.append(Paragraph(greeting, styles["BodyJustified"]))
    return elements


def _narrative_section(narrative: str, styles):
    elements = []
    # Split paragraphs on double newline
    paragraphs = [p.strip() for p in narrative.split("\n\n") if p.strip()]
    for p in paragraphs:
        elements.append(Paragraph(p, styles["BodyJustified"]))
    return elements


def _portfolio_highlights_table(stmt: CapitalAccountStatement, styles):
    elements = []
    elements.append(Paragraph("Portfolio Highlights", styles["SectionHeader"]))

    # Top 5 assets by NOI
    top_assets = sorted(
        stmt.fund_performance.assets,
        key=lambda a: a.in_place_noi,
        reverse=True,
    )[:5]

    data = [["Asset", "State", "SF", "Occupancy", "In-Place NOI", "YoY Δ"]]
    for a in top_assets:
        data.append([
            a.asset_name,
            a.state,
            f"{a.sf:,}",
            f"{a.occupancy_pct:.0f}%",
            f"${a.in_place_noi:,.0f}",
            f"{a.yoy_noi_change_pct:+.1f}%",
        ])

    t = Table(data, colWidths=[1.7 * inch, 0.5 * inch, 0.9 * inch, 0.9 * inch, 1.2 * inch, 0.7 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SNOWBALL_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK_GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    return elements


def _capital_account_table(stmt: CapitalAccountStatement, styles):
    elements = []
    elements.append(Paragraph("Capital Account Statement", styles["SectionHeader"]))

    data = [
        ["", "Amount (USD)"],
        ["Beginning Capital Balance", _money(stmt.beginning_capital_balance)],
        ["(+) Contributions This Period", _money(stmt.period_contributions)],
        ["(−) Distributions This Period", _money(stmt.period_distributions)],
        ["(+) Allocated Share of Net Income", _money(stmt.allocated_net_income)],
        ["Ending Capital Balance", _money(stmt.ending_capital_balance)],
        ["", ""],
        ["ITD Net IRR", _pct(stmt.itd_net_irr)],
        ["ITD Equity Multiple", _multiple(stmt.itd_equity_multiple)],
        ["Committed but Uncalled Capital", _money(stmt.committed_uncalled)],
        ["Remaining Unfunded Commitment", _money(stmt.remaining_unfunded_commitment)],
    ]

    t = Table(data, colWidths=[3.8 * inch, 2.0 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SNOWBALL_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK_GRAY),
        # Ending balance row emphasized
        ("BACKGROUND", (0, 5), (-1, 5), SNOWBALL_BLUE_LIGHT),
        ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 4), (-1, 4), 0.5, DARK_GRAY),
        ("LINEABOVE", (0, 7), (-1, 7), 1, SNOWBALL_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t)
    return elements


def _cad_section(stmt: CapitalAccountStatement, styles):
    """Additional block for Canadian feeder investors."""
    if stmt.investor.fund_vehicle != "CAD_FEEDER":
        return []

    elements = []
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Canadian Reporting Disclosures", styles["SectionHeader"]))

    data = [
        ["", "USD", "CAD"],
        [
            "FX Rate (USD/CAD)",
            "—",
            f"{stmt.fx_rate_usd_cad:.4f}",
        ],
        [
            "Ending Capital Balance",
            _money(stmt.ending_capital_balance),
            _money(stmt.ending_balance_cad or 0, "C$"),
        ],
        [
            f"Withholding Tax ({stmt.cad_withholding_rate * 100:.0f}%)",
            "—",
            _money(stmt.withholding_amount_cad or 0, "C$"),
        ],
    ]
    t = Table(data, colWidths=[3.0 * inch, 1.5 * inch, 1.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SNOWBALL_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK_GRAY),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "Withholding tax amounts shown reflect the applicable Canadian "
        "non-resident withholding rate applied to distributions. Investors "
        "should consult their own tax advisors regarding the treatment of "
        "distributions from the Canadian Feeder Fund.",
        styles["Disclosure"],
    ))
    return elements


def _footer(styles):
    elements = []
    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(
        width="100%", thickness=0.75, color=SNOWBALL_BLUE, spaceAfter=6
    ))
    elements.append(Paragraph(
        "Questions regarding this statement should be directed to "
        "Andres Aldrete, Head of Portfolio Management &nbsp;|&nbsp; "
        "andres@snowballdevelopments.com",
        styles["Footer"],
    ))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "This statement is confidential and intended solely for the named recipient. "
        "Not for distribution.",
        styles["Footer"],
    ))
    return elements


def generate_pdf(
    stmt: CapitalAccountStatement,
    narrative: str,
    reporting_period: str,
    out_dir: Path,
) -> Path:
    """
    Render one investor PDF and return its path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    last_name = stmt.investor.investor_name.split()[-1].replace(" ", "_")
    safe_quarter = reporting_period.replace(" ", "_")
    filename = f"{stmt.investor.fund_vehicle}_{stmt.investor.investor_id}_{last_name}_{safe_quarter}.pdf"
    path = out_dir / filename

    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.6 * inch,
        title=f"Snowball Developments — {reporting_period}",
        author="Snowball Developments",
    )

    styles = _build_styles()
    story = []
    story.extend(_letterhead(styles))
    story.extend(_investor_header(stmt, styles, reporting_period))
    story.extend(_narrative_section(narrative, styles))
    story.extend(_portfolio_highlights_table(stmt, styles))
    story.append(Spacer(1, 10))
    story.extend(_capital_account_table(stmt, styles))
    story.extend(_cad_section(stmt, styles))
    story.extend(_footer(styles))

    doc.build(story)
    return path
