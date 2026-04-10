"""
WSGI entry point for production deployment (gunicorn, Railway, etc.).

Local development still uses main.py. Production servers use this file,
which ensures demo data exists on first boot and exposes the Flask app
instance under the standard name `app` that gunicorn looks for.
"""
from pathlib import Path
from src.web_ui import create_app

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"


def _ensure_demo_data():
    """Build sample documents and roster on first boot if they don't exist yet."""
    sources_dir = DATA_DIR / "sample_sources"
    roster_file = DATA_DIR / "investor_roster.xlsx"

    if not sources_dir.exists() or not any(sources_dir.glob("*")):
        print("[boot] Building sample source documents...")
        from build_sample_sources import build_all as build_sources
        build_sources(sources_dir)

    if not roster_file.exists():
        print("[boot] Building sample investor roster...")
        from seed_data import build_all as build_roster
        build_roster(DATA_DIR)


_ensure_demo_data()
app = create_app()
