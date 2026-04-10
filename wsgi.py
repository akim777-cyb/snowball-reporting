"""
WSGI entry point for production deployment (gunicorn, Railway, etc.).

Local development still uses main.py. Production servers use this file,
which exposes the Flask app instance under the standard name `app`
that gunicorn looks for.
"""
from src.web_ui import create_app

app = create_app()
