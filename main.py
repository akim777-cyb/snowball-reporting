"""
Snowball Developments — Investor Reporting Automation
Single-command launcher.

Usage:
    python main.py              # Launches the web app at http://127.0.0.1:5050
    python main.py --port 8000  # Use a different port
"""
import argparse
import webbrowser
from threading import Timer
from pathlib import Path

from src.web_ui import create_app


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"


def _ensure_demo_data():
    """Make sure the demo data files exist so the 'Use Demo' buttons work."""
    sources_dir = DATA_DIR / "sample_sources"
    roster_file = DATA_DIR / "investor_roster.xlsx"

    if not sources_dir.exists() or not any(sources_dir.glob("*")):
        print("[setup] Building sample source documents...")
        from build_sample_sources import build_all as build_sources
        build_sources(sources_dir)

    if not roster_file.exists():
        print("[setup] Building sample investor roster...")
        from seed_data import build_all as build_roster
        build_roster(DATA_DIR)


def main():
    parser = argparse.ArgumentParser(
        description="Snowball Developments — Investor Reporting Automation"
    )
    parser.add_argument(
        "--port", type=int, default=5050,
        help="Port for the web app (default: 5050)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't automatically open the browser",
    )
    args = parser.parse_args()

    _ensure_demo_data()

    app = create_app()

    print()
    print("=" * 60)
    print("  SNOWBALL DEVELOPMENTS")
    print("  Investor Reporting Automation")
    print("=" * 60)
    print(f"  Open: http://127.0.0.1:{args.port}")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    if not args.no_browser:
        Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()

    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
