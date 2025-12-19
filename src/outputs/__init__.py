"""Output handlers for insights delivery."""

from .google_docs import GoogleDocsOutput
from .web_dashboard import create_app, WebDashboard

__all__ = ["GoogleDocsOutput", "create_app", "WebDashboard"]

