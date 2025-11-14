"""Compatibility module so existing commands can run `uvicorn app:app`."""

from backend.app import app

__all__ = ["app"]
