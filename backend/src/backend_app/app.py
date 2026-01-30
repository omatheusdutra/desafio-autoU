"""Application factory for Email Smart Reply."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from .config.settings import get_settings
from .presentation.controllers import api, batch, web
from .application.nlp import warmup_models

PACKAGE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PACKAGE_DIR.parent.parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend" / "src"


def create_app() -> FastAPI:
    settings = get_settings()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if settings.enable_warmup:
            await asyncio.to_thread(warmup_models)
        yield

    app = FastAPI(
        title=settings.app_name, version=settings.app_version, lifespan=lifespan
    )

    templates = Jinja2Templates(directory=str(FRONTEND_DIR / "pages"))
    app.state.templates = templates

    app.mount("/styles", StaticFiles(directory=str(FRONTEND_DIR / "styles")), name="styles")
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
    app.mount("/reports", StaticFiles(directory=str(settings.reports_dir)), name="reports")

    app.include_router(web.router)
    app.include_router(api.router, prefix="/api")
    app.include_router(batch.router)

    if settings.enable_rate_limit:
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[settings.rate_limit_default],
        )
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

    @app.middleware("http")
    async def block_dot_git(request, call_next):
        if request.url.path.startswith("/.git"):
            return HTMLResponse(status_code=404)
        return await call_next(request)

    return app


app = create_app()
