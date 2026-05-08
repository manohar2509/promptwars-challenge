import logging
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import HTTPException
from pydantic import ValidationError
from app.config import settings
from app.routes import pages, api

logger = logging.getLogger(__name__)

app = FastAPI(
    title="TravelAI",
    description="AI-powered travel planning engine",
    version="1.0.0",
)

# Static files and templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Include routers
app.include_router(pages.router)
app.include_router(api.router, prefix="/api")


def _is_html_request(request: Request) -> bool:
    """Check if the request expects HTML (browser) vs JSON (API)."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept and not request.url.path.startswith("/api")


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Return clean validation errors."""
    if _is_html_request(request):
        return HTMLResponse(
            content=_error_html("Invalid input", "Please check your form fields and try again."),
            status_code=422,
        )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Friendly HTML error pages for browser requests."""
    if _is_html_request(request):
        messages = {
            404: ("Page Not Found", "The page you're looking for doesn't exist."),
            400: ("Bad Request", str(exc.detail)),
            500: ("Something Went Wrong", "We encountered an issue. Please try again."),
        }
        title, desc = messages.get(exc.status_code, ("Error", str(exc.detail)))
        return HTMLResponse(content=_error_html(title, desc), status_code=exc.status_code)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all: never show raw tracebacks to users."""
    logger.exception("Unhandled error: %s", exc)
    if _is_html_request(request):
        return HTMLResponse(
            content=_error_html("Something Went Wrong", "We encountered an unexpected issue. Please try again later."),
            status_code=500,
        )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _error_html(title: str, message: str) -> str:
    """Render a minimal branded error page."""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — TravelAI</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50 min-h-screen flex items-center justify-center">
<div class="text-center px-6">
  <span class="text-6xl mb-6 block">🌍</span>
  <h1 class="text-3xl font-bold text-gray-900 mb-3">{title}</h1>
  <p class="text-gray-600 mb-8 max-w-md mx-auto">{message}</p>
  <a href="/" class="inline-block bg-blue-500 hover:bg-blue-700 text-white font-semibold py-3 px-8 rounded-xl transition-colors">
    ← Back to Home
  </a>
</div></body></html>"""


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "ok", "version": "1.0.0"}
