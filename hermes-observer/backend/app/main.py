"""Presence Observer — FastAPI application entry point.

Serves:
  /api/*   — read-only JSON APIs for state, decisions, proxy, logs
  /*       — React SPA static files (from frontend/dist after build)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import FRONTEND_DIST
from .routers.api import router as api_router

app = FastAPI(
    title="Presence Observer",
    description="Profile-aware control console for the Hermes Presence Kernel.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# Mount API routes.
app.include_router(api_router)

# Mount React SPA static files if the build directory exists.
_index_html = FRONTEND_DIST / "index.html"
if FRONTEND_DIST.is_dir() and _index_html.exists():
    # Serve static assets (JS, CSS, images) from /assets/*.
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    # SPA catch-all: any non-API route returns index.html for client-side routing.
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"API route not found: /{full_path}")
        # Check if requested file exists in dist (e.g. favicon.ico, robots.txt).
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_index_html))
else:
    @app.get("/")
    async def no_frontend():
        return {
            "message": "Presence Observer API is running. Frontend not built yet.",
            "hint": "Run 'npm run build' in the frontend directory, then restart.",
            "api_docs": "/api/docs",
        }
