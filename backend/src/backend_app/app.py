"""Application factory for Email Smart Reply."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config.settings import get_settings
from .controllers import api, batch, web

PACKAGE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PACKAGE_DIR.parent.parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend" / "src"


def create_app() -> FastAPI:
    settings = get_settings()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    templates = Jinja2Templates(directory=str(FRONTEND_DIR / "pages"))
    app.state.templates = templates

    app.mount("/styles", StaticFiles(directory=str(FRONTEND_DIR / "styles")), name="styles")
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
    app.mount("/reports", StaticFiles(directory=str(settings.reports_dir)), name="reports")

    app.include_router(web.router)
    app.include_router(api.router, prefix="/api")
    app.include_router(batch.router)

    return app


app = create_app()
