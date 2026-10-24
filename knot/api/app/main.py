from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_db

settings = get_settings()

app = FastAPI(
    title="Knot",
    # No public API docs in production: nothing about this service should be discoverable.
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)

api = APIRouter(prefix="/api")


@api.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"ok": True}


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
            if candidate.name in {"sw.js", "registerSW.js", "manifest.webmanifest"}:
                headers["Cache-Control"] = "no-cache"
            return FileResponse(candidate, headers=headers)
        return FileResponse(static_dir / "index.html", headers={"Cache-Control": "no-cache"})
