import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_db
from .purge import purge_forever
from . import live
from .routes import auth, home, invites, knot, me, push, rounds

settings = get_settings()


def _check_production_config() -> None:
    if not settings.is_production:
        return
    problems = []
    if settings.secret_key in ("", "dev-only-change-me") or len(settings.secret_key) < 32:
        problems.append("SECRET_KEY must be set to 32+ random characters")
    if not settings.owner_email:
        problems.append("OWNER_EMAIL must be set")
    if not settings.app_origin.startswith("https://"):
        problems.append("APP_ORIGIN must be the https:// address of the app")
    if problems:
        raise RuntimeError("Refusing to start: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(_: FastAPI):
    _check_production_config()
    task = asyncio.create_task(purge_forever())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="Knot",
    lifespan=lifespan,
    # No public API docs in production: nothing about this service should be discoverable.
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)


@app.middleware("http")
async def same_origin_writes(request: Request, call_next):
    """Defence in depth on top of SameSite cookies: in production, anything that changes data
    must come from the app's own origin."""
    if (
        settings.is_production
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api/")
        and request.headers.get("origin") != settings.app_origin
    ):
        return JSONResponse({"detail": {"code": "bad_origin", "message": "Not allowed."}}, status_code=403)
    return await call_next(request)


api = APIRouter(prefix="/api")


@api.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"ok": True}


api.include_router(auth.router)
api.include_router(invites.router)
api.include_router(me.router)
api.include_router(knot.router)
api.include_router(home.router)
api.include_router(rounds.router)
api.include_router(push.router)
api.include_router(live.router)  # /api/ws
app.include_router(api)


# ── Serve the built PWA (production: same origin as the API) ──────────────────

static_dir = Path(settings.static_dir).resolve()

if static_dir.is_dir():
    # Hashed build assets.
    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        """Serve real files (sw.js, manifest, icons) when they exist; otherwise index.html."""
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(static_dir):
            headers = {}
            # The service worker must never be cached, or updates get stuck on the phone.
            if candidate.name in {"sw.js", "registerSW.js", "push-sw.js", "manifest.webmanifest"}:
                headers["Cache-Control"] = "no-cache"
            return FileResponse(candidate, headers=headers)
        return FileResponse(static_dir / "index.html", headers={"Cache-Control": "no-cache"})
