"""
Generate realistic mock source documents that Andres's property managers
might actually send each quarter. Used by demo mode — dropping these
into the pipeline lets Brian see the full extraction workflow live.

Creates three files in data/sample_sources/:
  - q1_operating_statement.pdf  (a property management operating report)
  - q1_rent_roll.xlsx           (a rent roll from a different PM)
  - q1_argus_export.csv         (an ARGUS-style export for the remaining assets)
"""
from pathlib import Path
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER


def build_operating_statement_pdf(out_path: Path):
    """A property management operating statement PDF — looks like a real PM report."""
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"],
        fontSize=16, textColor=HexColor("#1a3a52"), spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"],
        fontSize=9, textColor=HexColor("#666666"), spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        fontSize=11, textColor=HexColor("#1a3a52"),
        spaceBefore=14, spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9, textColor=black, spaceAfter=6,
    )

    story = []
    story.append(Paragraph("TRI-STATE PROPERTY SERVICES, LLC", title_style))
    story.append(Paragraph(
        "Quarterly Operating Statement &nbsp;|&nbsp; Q1 2026 &nbsp;|&nbsp; Prepared for: Snowball Developments",
        sub_style,
    ))

    story.append(Paragraph(
        "The following operating summary covers five industrial assets under management "
        "for the period ending March 31, 2026. Occupancy, NOI, and year-over-year "
        "change figures are drawn from the property-level general ledger and reconciled "
        "to the underlying rent roll.",
        body_style,
    ))

    story.append(Paragraph("Asset Performance Summary", section_style))

    data = [
        ["Property", "State", "Rentable SF", "Occupancy", "YTD Annualized NOI", "YoY NOI Δ", "Est. Market Value"],
        ["Eastern Park",  "CT", "180,000", "95%",  "$1,620,000", "+8.5%",  "$21,000,000"],
        ["Mountainside",  "NJ",  "95,000", "98%",    "$935,000", "+6.2%",  "$14,500,000"],
        ["South Windsor", "CT", "145,000", "97%",  "$1,180,000", "+11.3%", "$16,200,000"],
        ["Danbury",       "CT", "125,000", "92%",    "$870,000", "+5.8%",  "$11,800,000"],
        ["Little Ferry",  "NJ",  "68,000", "100%",   "$720,000", "+9.4%",  "$10,500,000"],
    ]
    t = Table(data, colWidths=[1.3*inch, 0.5*inch, 0.9*inch, 0.8*inch, 1.3*inch, 0.8*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a3a52")),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.25, HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Paragraph("Notes to Operating Statement", section_style))
    story.append(Paragraph(
        "(1) Eastern Park signed a new 10-year anchor lease in January 2026, which "
        "contributed to the year-over-year NOI growth shown above. "
        "(2) South Windsor NOI reflects the full quarter impact of the 42% mark-to-market "
        "lease signed in February. "
        "(3) Little Ferry remains 100% occupied under the BioTrans lease, which is not "
        "scheduled for rollover until 2029. "
        "(4) Danbury occupancy reflects one unit vacancy that is under active negotiation. "
        "Market value estimates are prepared internally and should not be construed as "
        "third-party appraisals.",
        body_style,
    ))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Tri-State Property Services, LLC &nbsp;|&nbsp; 200 Summer Street, Stamford, CT 06901",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7,
                       textColor=HexColor("#888888"), alignment=TA_CENTER),
    ))

    doc.build(story)


def build_rent_roll_xlsx(out_path: Path):
    """A rent roll from a different PM covering a different set of assets."""
    rows = [
        # Bridgeport
        ("Bridgeport", "CT", 210_000, "Suite A - 80,000 SF", "Acme Logistics", "$7.85/SF", "Jul 2028", 100),
        ("Bridgeport", "CT", 210_000, "Suite B - 65,000 SF", "PrimePack Co.",   "$7.20/SF", "Mar 2027", 100),
        ("Bridgeport", "CT", 210_000, "Suite C - 40,000 SF", "Vacant",          "—",         "—",        0),
        ("Bridgeport", "CT", 210_000, "Suite D - 25,000 SF", "Northeast Parts", "$6.95/SF", "Dec 2026", 100),
        # Stratford
        ("Stratford",  "CT", 155_000, "Whole Building",      "Maritime Supply", "$6.80/SF", "Aug 2030", 94),
        # Waterbury
        ("Waterbury",  "CT", 135_000, "Whole Building",      "Regional Foods",  "$7.30/SF", "Jun 2032", 100),
        # Windsor Locks
        ("Windsor Locks", "CT", 175_000, "Suite 1 - 120,000 SF", "Cargo Systems", "$7.10/SF", "Nov 2029", 100),
        ("Windsor Locks", "CT", 175_000, "Suite 2 - 55,000 SF",  "Vacant",        "—",         "—",        0),
        # East Hartford
        ("East Hartford", "CT", 115_000, "Whole Building", "Atlantic Warehousing", "$7.05/SF", "Feb 2028", 95),
    ]

    df = pd.DataFrame(rows, columns=[
        "Property", "State", "Total SF", "Suite", "Tenant",
        "Rent PSF", "Lease Expiry", "Occupancy %",
    ])

    summary = pd.DataFrame([
        ("Bridgeport",    "CT", 210_000, 88,  1_380_000,  4.2, 17_500_000),
        ("Stratford",     "CT", 155_000, 94,  1_050_000,  7.1, 13_200_000),
        ("Waterbury",     "CT", 135_000, 100,   985_000, 12.6, 12_100_000),
        ("Windsor Locks", "CT", 175_000, 90,  1_220_000,  6.8, 14_700_000),
        ("East Hartford", "CT", 115_000, 95,    810_000,  9.2, 10_300_000),
    ], columns=[
        "Asset Name", "State", "SF", "Occupancy %", "Annualized NOI",
        "YoY NOI Change %", "Internal Valuation",
    ])

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Asset Summary", index=False)
        df.to_excel(writer, sheet_name="Rent Roll Detail", index=False)


def build_argus_export_csv(out_path: Path):
    """An ARGUS-style flat CSV export for the remaining assets."""
    rows = [
        ("Elizabeth",  "NJ", 85_000,   100, 925_000,  8.1, 12_800_000),
        ("Kearny",     "NJ", 72_000,    96, 780_000,  7.5, 10_900_000),
        ("Meriden",    "CT", 160_000,   82, 1_020_000, 3.4, 13_500_000),
        ("New Britain", "CT", 80_000,  100, 615_000, 10.8, 8_400_000),
    ]
    df = pd.DataFrame(rows, columns=[
        "asset_name", "state", "sf", "occupancy_pct",
        "in_place_noi", "yoy_noi_change_pct", "valuation_mark",
    ])
    df.to_csv(out_path, index=False)


def build_all(sources_dir: Path):
    sources_dir.mkdir(parents=True, exist_ok=True)
    build_operating_statement_pdf(sources_dir / "q1_operating_statement.pdf")
    build_rent_roll_xlsx(sources_dir / "q1_rent_roll.xlsx")
    build_argus_export_csv(sources_dir / "q1_argus_export.csv")


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sample_sources")
    build_all(out)
    print(f"Mock source documents written to {out}/")
