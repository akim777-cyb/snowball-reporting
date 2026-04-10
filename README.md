# Snowball Developments — Investor Reporting Automation

A fully automated pipeline that generates quarterly investor reports for Snowball Developments across three fund vehicles (GP Fund #1, GP Fund #2, and the Canadian Feeder Fund).

Built as a working prototype for the Snowball internship interview with Brian Ker and Andres Aldrete.

---

## What It Does

This tool eliminates two categories of manual quarterly work:

**1. Asset-side data entry (upstream pain):**
Property managers send operating statements, rent rolls, and ARGUS exports in different formats. The tool reads all of them — PDF, Excel, CSV — and extracts structured asset-level performance (name, SF, occupancy, NOI, YoY change, valuation) into a single review table.

**2. Reporter-side data entry (Andres's stated pain):**
Instead of manually entering data per investor into each quarterly report, the tool generates personalized capital account statements for every investor in every fund — correctly handling US dollars, Canadian dollars, FX conversion, and non-resident withholding tax — all from a single set of inputs.

**Two mandatory human approval gates** keep the system safe for investor communications:
- **Gate 1**: Andres reviews, edits, or regenerates the AI-drafted fund narrative for each of the three funds
- **Gate 2**: Every draft PDF appears in a thumbnail grid for spot-check approval before release

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# (Optional) Add your Anthropic API key for live narrative generation
cp .env.example .env
# Edit .env and add ANTHROPIC_API_KEY=sk-ant-...

# Launch the app
python main.py
```

The browser opens automatically to `http://127.0.0.1:5050`.

---

## Using the Pipeline

Click **Start Pipeline** on the landing page and walk through the seven steps. Each step has a **Use Demo** button that loads bundled sample data, so you can show the full workflow end-to-end without uploading any real files.

1. **Upload source documents** (or use demo) — drop in operating statements, rent rolls, ARGUS exports
2. **Review extracted assets** — the AI's extraction appears in an editable table; fix any wrong values inline
3. **Upload investor roster** (or use demo) — reconciliation runs automatically
4. **Enter quarter highlights** — 3-5 bullet points per fund (the only free-text input)
5. **Gate 1: Narrative review** — AI drafts one narrative per fund; approve, edit, or regenerate
6. **Generate PDFs** — background render with live progress
7. **Gate 2: Draft review** — thumbnail grid, click any PDF to preview, approve individually or in bulk
8. **Release** — approved PDFs move to `approved_pdfs/`

---

## Architecture

```
┌─────────────────────────┐
│  Source Documents       │  ← Operating stmts, rent rolls, ARGUS exports
│  (PDF / Excel / CSV)    │     (in production: property manager feeds)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Document Intelligence  │  Claude API extracts structured asset data
│  (Claude Sonnet 4)      │  Falls back to fixtures if API unreachable
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Review & Edit          │  Andres corrects any extraction errors
│  (in-browser table)     │  inline before confirming
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Investor Roster        │  ← Excel upload
│  + Reconciliation       │     (in production: Juniper Square API)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Fund Narrative Gen     │  Claude API writes one narrative per fund
│  (Claude Sonnet 4)      │  using extracted perf data + highlights
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  ★ GATE 1 ★             │  Andres reviews/edits/regenerates in browser
│  Narrative approval     │  Nothing downstream runs until approved
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Per-Investor Calc      │  Capital account rollforward:
│                         │  - Beginning / ending balance
│                         │  - Period contributions / distributions
│                         │  - Allocated net income
│                         │  - Committed but uncalled (separate line)
│                         │  - CAD conversion + withholding (feeder)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  PDF Generation         │  Branded letters with Snowball #2596be
│  (ReportLab)            │  Background render with progress polling
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  ★ GATE 2 ★             │  Thumbnail grid review in browser
│  Draft PDF approval     │  Click to preview, approve/reject/bulk
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Release                │  In demo: copies to approved_pdfs/
│                         │  In production: posts to Juniper Square
└─────────────────────────┘
```

---

## Production Path: Moving from Demo to Real Snowball Pipeline

The tool is structured so that only two modules change when moving from demo to production. The rest of the codebase (schemas, calculations, narrative generation, PDF rendering, Flask UI) stays identical.

### 1. Replace `src/ingest.py` with a Juniper Square API connector

**Current (demo):** Reads investor data from `investor_roster.xlsx`.

**Production:** Replace the three functions in `ingest.py` with calls to the Juniper Square partner API:
- `load_investors()` → `jsq_client.list_investors(fund_id)` — returns the same Pydantic `Investor` schema
- `load_fund_performance()` → `jsq_client.get_fund_performance(fund_id, quarter)` — same `FundPerformance` schema
- `load_quarter_inputs()` → can stay file-based, or move to a web form Andres fills out each quarter

JSQ's API provides investor roster, commitment, contribution, distribution, and capital account data directly. Because the rest of the system depends only on the Pydantic schemas in `src/schemas.py`, nothing downstream needs to change.

### 2. Extend `src/document_intelligence.py` to Snowball's actual source documents

**Current (demo):** Extracts from three sample source documents (operating statement PDF, rent roll Excel, ARGUS CSV) using Claude Sonnet 4.

**Production:** Wire `extract_assets_from_document()` into whatever Andres's property managers actually send each quarter. The extraction prompt in `_EXTRACTION_PROMPT` is format-agnostic — it works on any document that contains asset performance data. For recurring PM reports that arrive in a stable format, the extraction layer can be fine-tuned with a few examples to improve accuracy.

### 3. Replace the release layer with JSQ portal posting

**Current (demo):** Approved PDFs copy to `approved_pdfs/`.

**Production:** In the `release()` route of `src/web_ui.py`, replace the `shutil.copy2` loop with calls to JSQ's document upload endpoint, posting each PDF to the corresponding investor's portal view.

### 4. Add authentication and audit logging

The current tool assumes a single trusted operator. In production, add:
- SSO login (Google/Okta) for access control
- Per-action audit log (who generated, who approved, when released) — JSQ requires this for SOC 2 compliance
- Per-session state instead of the global `STATE` dict in `web_ui.py`

### What Stays Exactly the Same

- `src/schemas.py` — data validation (production and demo speak the same shape)
- `src/calculations.py` — capital account math
- `src/narrative.py` — Claude API narrative generation
- `src/pdf_generator.py` — ReportLab branded PDFs
- `templates/` — entire UI
- `static/style.css` — branding and layout
- Approval gate logic — human-in-the-loop is not optional in production either

---

## Project Structure

```
snowball_reporting/
├── main.py                       # Single-command launcher
├── build_sample_sources.py       # Generates mock PM documents for demo
├── seed_data.py                  # Generates mock investor roster for demo
├── requirements.txt
├── .env.example
├── README.md
│
├── src/
│   ├── schemas.py                # Pydantic validation
│   ├── ingest.py                 # Excel ingestion (PRODUCTION SWAP POINT)
│   ├── document_intelligence.py  # Claude API asset extraction
│   ├── calculations.py           # Capital account rollforward
│   ├── narrative.py              # Claude API narrative generation
│   ├── pdf_generator.py          # ReportLab branded PDFs
│   └── web_ui.py                 # Unified Flask application
│
├── templates/                    # Jinja2 templates for the 7-step wizard
│   ├── base.html                 # Layout with progress stepper
│   ├── landing.html              # Start page
│   ├── assets.html               # Upload & review extracted assets
│   ├── investors.html            # Upload roster + reconciliation
│   ├── highlights.html           # Free-text quarter highlights
│   ├── narratives.html           # Gate 1 — narrative approval
│   ├── generate.html             # PDF generation progress
│   ├── review_pdfs.html          # Gate 2 — thumbnail grid approval
│   └── released.html             # Final confirmation
│
├── static/
│   └── style.css                 # Snowball-branded UI (#2596be)
│
├── data/
│   ├── investor_roster.xlsx      # Mock 20-investor roster
│   └── sample_sources/           # Mock PM documents for the demo
│       ├── q1_operating_statement.pdf
│       ├── q1_rent_roll.xlsx
│       └── q1_argus_export.csv
│
├── examples/                     # Example output PDFs (pre-rendered)
│   ├── example_GP1_US_investor.pdf
│   ├── example_GP2_US_investor.pdf
│   └── example_CAD_feeder_investor.pdf
│
├── uploads/                      # Runtime — user-uploaded files
├── approved_narratives/          # Runtime — Gate 1 outputs
├── draft_pdfs/                   # Runtime — pre-Gate 2 drafts
└── approved_pdfs/                # Runtime — post-release
```

---

## Demo Mode Notes

The tool works completely offline if no Anthropic API key is set:

- **Narrative generation** falls back to hand-written example narratives in Brian Ker's voice (stored in `src/web_ui.py`)
- **Asset extraction** falls back to deterministic fixtures keyed by source document filename

This means the interview demo runs reliably on any laptop with Python installed, even without internet access. With an API key, both narrative generation and asset extraction become fully live.

---

## Technical Stack

- **Python 3.11+**
- **Flask** — web UI
- **Pydantic** — data validation
- **Anthropic SDK** — Claude Sonnet 4 for narrative and extraction
- **ReportLab** — branded PDF generation
- **PyMuPDF** — PDF text extraction and thumbnail rendering
- **pandas + openpyxl** — Excel ingestion

---

## For Interview Demo

To walk Brian through the tool live:

1. `python main.py` — launches the app and opens the browser
2. Click **Start Pipeline**
3. On the Assets screen, click **Load Demo & Extract** — 14 assets extract from 3 source documents (one PDF, one Excel, one CSV)
4. Fix any value inline to show the edit workflow, click **Confirm & Continue**
5. On Investors, click **Load Demo Roster** — reconciliation check passes
6. Continue through Highlights (pre-populated), Narratives (Gate 1), PDF generation, and PDF review (Gate 2)
7. Release

Total demo time: ~3 minutes. Everything after the first click runs without terminal interaction.
