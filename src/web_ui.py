"""
Unified Flask web application for Snowball Developments' quarterly
investor reporting pipeline. Runs end-to-end with no terminal interaction.
"""
import shutil
import threading
from pathlib import Path

import fitz  # pymupdf
from flask import (
    Flask, render_template, request, redirect, url_for,
    send_from_directory, jsonify, flash, Response,
)

from .schemas import (
    AssetPerformance, FundPerformance, Investor,
    QuarterInputs, FundVehicle,
)
from .document_intelligence import extract_from_multiple
from .ingest import load_investors, validate_reconciliation
from .narrative import (
    generate_narrative, save_narrative, FUND_DISPLAY_NAMES,
)
from .calculations import compute_statements
from .pdf_generator import generate_pdf


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"
APPROVED_NARRATIVES = PROJECT_ROOT / "approved_narratives"
DRAFT_PDFS = PROJECT_ROOT / "draft_pdfs"
APPROVED_PDFS = PROJECT_ROOT / "approved_pdfs"
SAMPLE_SOURCES = PROJECT_ROOT / "data" / "sample_sources"
SAMPLE_INVESTOR_ROSTER = PROJECT_ROOT / "data" / "investor_roster.xlsx"


# Single-session in-memory state (single-operator desktop tool).
STATE = {
    "reporting_period": "Q1 2026",
    "fx_rate_usd_cad": 1.3650,
    "cad_withholding_rate": 0.15,
    "extracted_assets": [],
    "source_doc_names": [],
    "investors": [],
    "reconciliation_warnings": [],
    "highlights": {"GP1": [], "GP2": [], "CAD_FEEDER": []},
    "narratives": {
        "GP1": {"text": "", "approved": False},
        "GP2": {"text": "", "approved": False},
        "CAD_FEEDER": {"text": "", "approved": False},
    },
    "pdf_gen_status": "idle",
    "pdf_gen_progress": 0,
    "pdf_gen_total": 0,
    "draft_pdf_decisions": {},
}


def _build_fund_performance() -> dict:
    gp1_assets = STATE["extracted_assets"]
    gp2_assets = [
        AssetPerformance(
            asset_name="Norwalk Industrial", state="CT", sf=120_000,
            occupancy_pct=100.0, in_place_noi=870_000,
            yoy_noi_change_pct=0.0, valuation_mark=11_800_000,
        ),
        AssetPerformance(
            asset_name="Paterson Logistics", state="NJ", sf=95_000,
            occupancy_pct=85.0, in_place_noi=620_000,
            yoy_noi_change_pct=0.0, valuation_mark=8_900_000,
        ),
        AssetPerformance(
            asset_name="North Haven", state="CT", sf=105_000,
            occupancy_pct=95.0, in_place_noi=745_000,
            yoy_noi_change_pct=0.0, valuation_mark=9_700_000,
        ),
    ]
    return {
        "GP1": FundPerformance(
            fund_vehicle="GP1", quarter_end_nav=168_500_000,
            quarterly_distribution_per_unit=0.45, ytd_net_irr=14.2,
            itd_net_irr=17.8, ytd_equity_multiple=1.08,
            itd_equity_multiple=1.42, fund_unfunded_commitment=0,
            assets=gp1_assets,
        ),
        "GP2": FundPerformance(
            fund_vehicle="GP2", quarter_end_nav=10_250_000,
            quarterly_distribution_per_unit=0.0, ytd_net_irr=0.0,
            itd_net_irr=0.0, ytd_equity_multiple=1.0,
            itd_equity_multiple=1.0, fund_unfunded_commitment=15_000_000,
            assets=gp2_assets,
        ),
        "CAD_FEEDER": FundPerformance(
            fund_vehicle="CAD_FEEDER", quarter_end_nav=5_200_000,
            quarterly_distribution_per_unit=0.42, ytd_net_irr=13.5,
            itd_net_irr=16.9, ytd_equity_multiple=1.07,
            itd_equity_multiple=1.38, fund_unfunded_commitment=0,
            assets=gp1_assets,
        ),
    }


def _quarter_inputs() -> QuarterInputs:
    return QuarterInputs(
        reporting_period=STATE["reporting_period"],
        fx_rate_usd_cad=STATE["fx_rate_usd_cad"],
        cad_withholding_rate=STATE["cad_withholding_rate"],
        highlights_gp1=STATE["highlights"]["GP1"],
        highlights_gp2=STATE["highlights"]["GP2"],
        highlights_cad=STATE["highlights"]["CAD_FEEDER"],
    )


def _progress_pct() -> int:
    """Return a 0-100 integer reflecting overall pipeline progress (for header bar)."""
    steps = [
        bool(STATE["extracted_assets"]),
        bool(STATE["investors"]),
        any(STATE["highlights"].values()),
        all(n["approved"] for n in STATE["narratives"].values()),
        STATE["pdf_gen_status"] == "done",
        any(d == "approved" for d in STATE["draft_pdf_decisions"].values()),
    ]
    return int(sum(steps) / len(steps) * 100)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    app.secret_key = "snowball-demo-key"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    @app.context_processor
    def inject_globals():
        return {
            "state": STATE,
            "progress_pct": _progress_pct(),
            "current_step": _current_step(),
        }

    # ---------- Landing ----------
    @app.route("/")
    def index():
        return render_template("landing.html")

    @app.route("/reset", methods=["POST"])
    def reset():
        STATE["extracted_assets"] = []
        STATE["source_doc_names"] = []
        STATE["investors"] = []
        STATE["reconciliation_warnings"] = []
        STATE["highlights"] = {"GP1": [], "GP2": [], "CAD_FEEDER": []}
        for k in STATE["narratives"]:
            STATE["narratives"][k] = {"text": "", "approved": False}
        STATE["pdf_gen_status"] = "idle"
        STATE["pdf_gen_progress"] = 0
        STATE["pdf_gen_total"] = 0
        STATE["draft_pdf_decisions"] = {}
        for d in [DRAFT_PDFS, APPROVED_PDFS, APPROVED_NARRATIVES]:
            if d.exists():
                shutil.rmtree(d)
        return redirect(url_for("index"))

    # ---------- Step 1: Assets ----------
    @app.route("/assets", methods=["GET", "POST"])
    def assets():
        if request.method == "POST":
            uploaded = []
            for f in request.files.getlist("files"):
                if f.filename:
                    dest = UPLOAD_DIR / f.filename
                    f.save(dest)
                    uploaded.append(dest)
            if uploaded:
                STATE["extracted_assets"] = extract_from_multiple(uploaded)
                STATE["source_doc_names"] = [p.name for p in uploaded]
            return redirect(url_for("assets"))
        return render_template("assets.html", assets=STATE["extracted_assets"])

    @app.route("/assets/load-demo", methods=["POST"])
    def load_demo_assets():
        if not SAMPLE_SOURCES.exists() or not any(SAMPLE_SOURCES.iterdir()):
            flash("Sample sources not found. Run: python build_sample_sources.py", "error")
            return redirect(url_for("assets"))
        paths = sorted(SAMPLE_SOURCES.glob("*"))
        STATE["extracted_assets"] = extract_from_multiple(paths)
        STATE["source_doc_names"] = [p.name for p in paths]
        return redirect(url_for("assets"))

    @app.route("/assets/update", methods=["POST"])
    def update_assets():
        updated = []
        n = int(request.form.get("row_count", 0))
        for i in range(n):
            name = request.form.get(f"asset_name_{i}", "").strip()
            if not name:
                continue
            try:
                updated.append(AssetPerformance(
                    asset_name=name,
                    state=request.form.get(f"state_{i}", "").strip(),
                    sf=int(float(request.form.get(f"sf_{i}", 0) or 0)),
                    occupancy_pct=float(request.form.get(f"occupancy_pct_{i}", 0) or 0),
                    in_place_noi=float(request.form.get(f"in_place_noi_{i}", 0) or 0),
                    yoy_noi_change_pct=float(request.form.get(f"yoy_noi_change_pct_{i}", 0) or 0),
                    valuation_mark=float(request.form.get(f"valuation_mark_{i}", 0) or 0),
                ))
            except Exception as e:
                flash(f"Error on row {i+1}: {e}", "error")
                return redirect(url_for("assets"))
        STATE["extracted_assets"] = updated
        return redirect(url_for("investors"))

    # ---------- Step 2: Investors ----------
    @app.route("/investors", methods=["GET", "POST"])
    def investors():
        if request.method == "POST":
            f = request.files.get("roster")
            if f and f.filename:
                dest = UPLOAD_DIR / f.filename
                f.save(dest)
                STATE["investors"] = load_investors(dest)
                funds = _build_fund_performance()
                STATE["reconciliation_warnings"] = validate_reconciliation(
                    STATE["investors"], funds
                )
            return redirect(url_for("investors"))
        return render_template(
            "investors.html",
            investors=STATE["investors"],
            warnings=STATE["reconciliation_warnings"],
        )

    @app.route("/investors/load-demo", methods=["POST"])
    def load_demo_investors():
        if not SAMPLE_INVESTOR_ROSTER.exists():
            flash("Sample roster not found.", "error")
            return redirect(url_for("investors"))
        STATE["investors"] = load_investors(SAMPLE_INVESTOR_ROSTER)
        funds = _build_fund_performance()
        STATE["reconciliation_warnings"] = validate_reconciliation(
            STATE["investors"], funds
        )
        return redirect(url_for("investors"))

    # ---------- Step 3: Highlights ----------
    @app.route("/highlights", methods=["GET", "POST"])
    def highlights():
        if request.method == "POST":
            for code in ["GP1", "GP2", "CAD_FEEDER"]:
                raw = request.form.get(f"highlights_{code}", "")
                bullets = [
                    line.strip("- •\t").strip()
                    for line in raw.split("\n") if line.strip()
                ]
                STATE["highlights"][code] = bullets
            # Clear narratives so they regenerate with new highlights
            for k in STATE["narratives"]:
                STATE["narratives"][k] = {"text": "", "approved": False}
            return redirect(url_for("narratives"))

        if not any(STATE["highlights"].values()):
            STATE["highlights"] = _demo_highlights()
        return render_template("highlights.html")

    # ---------- Step 4: Narratives (Gate 1) ----------
    @app.route("/narratives")
    def narratives():
        funds = _build_fund_performance()
        for code in ["GP1", "GP2", "CAD_FEEDER"]:
            if not STATE["narratives"][code]["text"]:
                STATE["narratives"][code]["text"] = _try_generate(
                    funds[code], STATE["highlights"][code]
                )

        all_approved = all(n["approved"] for n in STATE["narratives"].values())
        fund_cards = [{
            "code": code,
            "name": FUND_DISPLAY_NAMES[code],
            "performance": funds[code],
            "narrative": STATE["narratives"][code]["text"],
            "approved": STATE["narratives"][code]["approved"],
            "highlights": STATE["highlights"][code],
        } for code in ["GP1", "GP2", "CAD_FEEDER"]]

        return render_template(
            "narratives.html",
            funds=fund_cards,
            all_approved=all_approved,
        )

    @app.route("/narratives/<code>/regenerate", methods=["POST"])
    def regen_narrative(code):
        funds = _build_fund_performance()
        STATE["narratives"][code]["text"] = _try_generate(
            funds[code], STATE["highlights"][code]
        )
        STATE["narratives"][code]["approved"] = False
        return redirect(url_for("narratives"))

    @app.route("/narratives/<code>/save", methods=["POST"])
    def save_narrative_edit(code):
        STATE["narratives"][code]["text"] = request.form.get("narrative", "")
        STATE["narratives"][code]["approved"] = False
        return redirect(url_for("narratives"))

    @app.route("/narratives/<code>/approve", methods=["POST"])
    def approve_narrative(code):
        text = request.form.get("narrative", "")
        STATE["narratives"][code]["text"] = text
        STATE["narratives"][code]["approved"] = True
        save_narrative(text, code, STATE["reporting_period"], APPROVED_NARRATIVES)
        return redirect(url_for("narratives"))

    @app.route("/narratives/<code>/unapprove", methods=["POST"])
    def unapprove_narrative(code):
        STATE["narratives"][code]["approved"] = False
        return redirect(url_for("narratives"))

    # ---------- Step 5: Generate PDFs ----------
    @app.route("/generate", methods=["GET", "POST"])
    def generate():
        if request.method == "POST":
            _start_pdf_generation()
            return redirect(url_for("generate"))
        return render_template("generate.html")

    @app.route("/generate/status")
    def generate_status():
        return jsonify({
            "status": STATE["pdf_gen_status"],
            "progress": STATE["pdf_gen_progress"],
            "total": STATE["pdf_gen_total"],
        })

    # ---------- Step 6: Review PDFs (Gate 2) ----------
    @app.route("/review-pdfs")
    def review_pdfs():
        if not DRAFT_PDFS.exists():
            return redirect(url_for("generate"))
        pdfs = sorted(DRAFT_PDFS.glob("*.pdf"))
        items = []
        for p in pdfs:
            items.append({
                "filename": p.name,
                "label": _pretty_name(p.name),
                "fund": p.name.split("_")[0],
                "decision": STATE["draft_pdf_decisions"].get(p.name, "pending"),
            })
        approved_count = sum(1 for i in items if i["decision"] == "approved")
        rejected_count = sum(1 for i in items if i["decision"] == "rejected")
        pending_count = sum(1 for i in items if i["decision"] == "pending")
        return render_template(
            "review_pdfs.html",
            items=items,
            approved_count=approved_count,
            rejected_count=rejected_count,
            pending_count=pending_count,
        )

    @app.route("/draft-pdf/<filename>")
    def serve_draft_pdf(filename):
        return send_from_directory(DRAFT_PDFS, filename)

    @app.route("/draft-thumbnail/<filename>")
    def draft_thumbnail(filename):
        path = DRAFT_PDFS / filename
        if not path.exists():
            return Response(status=404)
        doc = fitz.open(str(path))
        pix = doc[0].get_pixmap(dpi=80)
        return Response(pix.tobytes("png"), mimetype="image/png")

    @app.route("/review-pdfs/decision", methods=["POST"])
    def pdf_decision():
        data = request.get_json()
        filename = data.get("filename")
        decision = data.get("decision")
        if filename and decision in ("approved", "rejected", "pending"):
            STATE["draft_pdf_decisions"][filename] = decision
        return jsonify({"ok": True})

    @app.route("/review-pdfs/bulk", methods=["POST"])
    def bulk_decision():
        decision = request.form.get("decision", "approved")
        for pdf in DRAFT_PDFS.glob("*.pdf"):
            STATE["draft_pdf_decisions"][pdf.name] = decision
        return redirect(url_for("review_pdfs"))

    @app.route("/release", methods=["POST"])
    def release():
        APPROVED_PDFS.mkdir(exist_ok=True)
        released = 0
        for pdf in DRAFT_PDFS.glob("*.pdf"):
            if STATE["draft_pdf_decisions"].get(pdf.name) == "approved":
                shutil.copy2(pdf, APPROVED_PDFS / pdf.name)
                released += 1
        rejected = sum(
            1 for d in STATE["draft_pdf_decisions"].values() if d == "rejected"
        )
        return render_template(
            "released.html", released=released, rejected=rejected,
        )

    @app.route("/approved-pdf/<filename>")
    def serve_approved_pdf(filename):
        return send_from_directory(APPROVED_PDFS, filename)

    return app


# ---------- Helpers ----------

def _current_step() -> int:
    if not STATE["extracted_assets"]:
        return 1
    if not STATE["investors"]:
        return 2
    if not any(STATE["highlights"].values()):
        return 3
    if not all(n["approved"] for n in STATE["narratives"].values()):
        return 4
    if STATE["pdf_gen_status"] != "done":
        return 5
    if not any(d == "approved" for d in STATE["draft_pdf_decisions"].values()):
        return 6
    return 7


def _try_generate(fund, highlights) -> str:
    import os
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            return generate_narrative(
                fund=fund, highlights=highlights,
                reporting_period=STATE["reporting_period"],
            )
    except Exception as e:
        print(f"[narrative] API failed, using fallback: {e}")
    return _FALLBACK_NARRATIVES.get(fund.fund_vehicle, "")


def _start_pdf_generation():
    def _run():
        try:
            STATE["pdf_gen_status"] = "running"
            STATE["pdf_gen_progress"] = 0
            if DRAFT_PDFS.exists():
                shutil.rmtree(DRAFT_PDFS)
            DRAFT_PDFS.mkdir(parents=True)

            funds = _build_fund_performance()
            quarter = _quarter_inputs()
            statements = compute_statements(STATE["investors"], funds, quarter)
            STATE["pdf_gen_total"] = len(statements)

            for stmt in statements:
                narrative = STATE["narratives"][stmt.investor.fund_vehicle]["text"]
                generate_pdf(
                    stmt=stmt, narrative=narrative,
                    reporting_period=STATE["reporting_period"],
                    out_dir=DRAFT_PDFS,
                )
                STATE["pdf_gen_progress"] += 1

            STATE["draft_pdf_decisions"] = {
                p.name: "pending" for p in DRAFT_PDFS.glob("*.pdf")
            }
            STATE["pdf_gen_status"] = "done"
        except Exception as e:
            print(f"[pdf generation] error: {e}")
            STATE["pdf_gen_status"] = "error"

    threading.Thread(target=_run, daemon=True).start()


def _pretty_name(filename: str) -> str:
    parts = filename.replace(".pdf", "").split("_")
    if len(parts) >= 3:
        return f"{parts[2]}"
    return filename


def _demo_highlights():
    return {
        "GP1": [
            "Portfolio occupancy reached 94% on a trailing basis, with ~350K SF of leases pending execution that will push occupancy toward 98% by Q2.",
            "Signed a new 10-year lease at South Windsor at $8.75 PSF NNN, a 42% mark-to-market premium over the prior in-place rent.",
            "Solar program expanded to 9 assets totaling 500K+ SF, now generating $245K in annual income at ~$0.50 PSF.",
            "Completed the South Windsor refinancing at $9.5M against a $9.0M total cost basis, returning equity to the partnership.",
            "Waterbury and Meriden executed 4 acres of outdoor storage leases, adding incremental cash flow with minimal capex.",
        ],
        "GP2": [
            "Three initial assets acquired in Q1: Norwalk Industrial, Paterson Logistics, and North Haven, totaling 320K SF for approximately $30.4M.",
            "Pipeline includes 6 assets under contract representing 600K SF, with closings anticipated between February and April.",
            "Fund is on track to be fully deployed by the end of 2026.",
            "Value-add thesis unchanged: acquire land-heavy assets at below-replacement-cost basis in the Tri-State industrial market.",
        ],
        "CAD_FEEDER": [
            "The Canadian Feeder participated pro rata in GP Fund #1's Q1 activity, including the South Windsor refinancing and solar program expansion.",
            "FX conditions remained stable through the quarter at approximately 1.365 USD/CAD.",
            "No changes to the Canadian non-resident withholding rate of 15% on distributions.",
            "Eastern Canada expansion under evaluation for potential future feeder vehicles.",
        ],
    }


_FALLBACK_NARRATIVES = {
    "GP1": """Q1 2026 was a quarter of execution rather than headlines. Portfolio occupancy moved to 94% on a trailing basis, and with roughly 350,000 square feet of leases pending execution, we expect to be near 98% leased by the end of Q2. That is the outcome of eighteen months of patient underwriting combined with two quarters of concentrated leasing effort, and it validates the central thesis we bought into: that Tri-State industrial rents were materially below market and that physical improvements would unlock the gap.

The clearest example this quarter was South Windsor. We signed a new 10-year lease at $8.75 PSF NNN, a 42% premium to the prior in-place rent. We also closed on the South Windsor refinancing at $9.5 million against a total cost basis of $9.0 million, returning capital to the partnership while we continue to hold the asset. That is the value-add playbook working exactly as designed: buy at a low basis, improve the asset, push rents to market, and recapitalize.

Beyond the core portfolio, the solar program continues to outperform its own underwriting. We now have nine assets in the program totaling more than 500,000 square feet and generating approximately $245,000 in annual income, roughly $0.50 PSF. None of this was modeled at acquisition. Waterbury and Meriden also executed four acres of outdoor storage leases during the quarter, adding incremental cash flow without meaningful capex.

Looking to Q2, the priority is converting the pending lease pipeline into executed paper and continuing to monetize excess land across the Connecticut portfolio. The two assets that sat mostly vacant through 2025 are showing real activity, and we expect to report resolution on at least one of them by the next letter.

As always, please reach out if you would like to walk through the portfolio in more detail.""",

    "GP2": """GP Fund #2 deployed its first capital in Q1 2026. We closed on three assets — Norwalk Industrial, Paterson Logistics, and North Haven — totaling approximately 320,000 square feet for $30.4 million. Each acquisition was sourced off-market and priced well below replacement cost, consistent with the fund's stated strategy of acquiring land-heavy industrial assets in the Tri-State area.

The current pipeline includes six additional assets under contract representing another 600,000 square feet, with closings anticipated between February and April. If the pipeline executes as expected, the fund will be substantially deployed by the end of 2026.

The value-add thesis remains exactly as underwritten at fund launch. Connecticut industrial rents continue to sit 30 to 40 percent below New Jersey comparables despite similar functional characteristics. Physical improvements and lease rollover remain the primary drivers of value creation, and the expanding solar program from Fund #1 is informing how we underwrite land on new acquisitions.

For investors who have not yet fully funded their commitments, we appreciate your continued patience as we deploy capital on a disciplined basis. Quarterly capital calls are being structured to match deployment pace, and the Q2 call schedule will be communicated separately. Investors with questions about the pacing of contributions or the deployment timeline are encouraged to reach out directly.

We will continue to prioritize quality of basis over speed of deployment. The goal for 2026 is a fully invested portfolio that mirrors the land-maximization, low-basis characteristics that have defined Snowball's track record to date.""",

    "CAD_FEEDER": """The Canadian Feeder Fund participated pro rata in GP Fund #1's activity during Q1 2026. That included the South Windsor refinancing, which returned capital to the underlying partnership, and the continued expansion of the solar program across the Connecticut and New Jersey portfolio. Feeder investors see through to the same asset-level performance as the direct GP Fund #1 partners, adjusted for the feeder structure and applicable Canadian tax treatment.

The underlying portfolio delivered another quarter of operational progress. Occupancy moved toward 94% on a trailing basis, with pending leases that should bring the portfolio close to 98% leased by the end of Q2. South Windsor signed a new 10-year lease at a 42% premium to the prior rent, and the solar program now contributes approximately $245,000 in annual income across nine assets.

FX conditions were stable through the quarter, with the USD/CAD rate averaging approximately 1.365. There were no changes to the Canadian non-resident withholding rate, which remains at 15% on distributions. As a reminder, withholding amounts shown on your capital account statement reflect the rate applied to distributions for the reporting period — investors should consult their own tax advisors regarding the treatment of distributions in their individual circumstances.

Looking forward, we continue to evaluate opportunities for an Eastern Canada expansion that would complement the Tri-State portfolio. Any such initiative would be communicated well in advance and structured with feeder investors in mind.

As always, please reach out with any questions regarding your account or the underlying portfolio.""",
}
