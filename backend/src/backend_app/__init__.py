"""backend_app package exports the FastAPI application factory."""

from .app import app, create_app

__all__ = ["app", "create_app"]
