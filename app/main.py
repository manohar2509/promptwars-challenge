"""FastAPI application entry point for the TravelAI planning engine.

Configures middleware (CORS, GZip, security headers, rate limiting),
exception handlers, static files, templates, and route mounting.
"""

import html
import logging
import os
import time
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.routes import api, pages

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related HTTP headers to every response.

    Headers follow OWASP recommendations for web applications:
    - ``X-Content-Type-Options``: prevent MIME sniffing.
    - ``X-Frame-Options``: prevent clickjacking.
    - ``X-XSS-Protection``: legacy XSS filter hint.
    - ``Referrer-Policy``: limit referrer information leakage.
    - ``Permissions-Policy``: restrict browser feature access.
    - ``Strict-Transport-Security``: enforce HTTPS (production only).
    - ``Content-Security-Policy``: restrict resource origins.
    """

    async def dispatch(self, request: Request, call_next):
        """Attach security headers to the outgoing response."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(self)"
        )
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.tailwindcss.com https://unpkg.com https://maps.googleapis.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://*.googleapis.com https://*.gstatic.com; "
            "connect-src 'self' https://*.googleapis.com; "
            "frame-src https://*.google.com; "
            "font-src 'self' https://fonts.gstatic.com"
        )
        return response


# ---------------------------------------------------------------------------
# Rate Limiting Middleware
# ---------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter per client IP.

    Rejects requests that exceed ``rate_limit_per_minute`` with HTTP 429.
    Only applied to ``/api/`` routes to avoid blocking static assets.
    """

    def __init__(self, app: ASGIApp, requests_per_minute: int = 30) -> None:
        super().__init__(app)
        self.rpm = requests_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        """Check rate limit before forwarding the request."""
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = [t for t in self._hits[client_ip] if now - t < 60]
        self._hits[client_ip] = window

        # Prune stale IPs every 100 requests to prevent memory leaks
        if sum(len(v) for v in self._hits.values()) > 500:
            stale = [ip for ip, hits in self._hits.items() if not hits]
            for ip in stale:
                del self._hits[ip]

        if len(window) >= self.rpm:
            logger.warning("Rate limit exceeded for %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait and try again."},
                headers={"Retry-After": "60"},
            )

        self._hits[client_ip].append(now)
        return await call_next(request)


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TravelAI",
    description="AI-powered travel planning engine using Google Gemini, Maps, and Cloud.",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Middleware (order matters — outermost runs first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["HX-Redirect"],
)

# Static files and templates
_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")
_templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

# Include routers
app.include_router(pages.router)
app.include_router(api.router, prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_html_request(request: Request) -> bool:
    """Check if the request expects HTML (browser) vs JSON (API)."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept and not request.url.path.startswith("/api")


def _error_html(title: str, message: str) -> str:
    """Render a minimal branded error page with escaped content.

    All dynamic content is HTML-escaped to prevent reflected XSS.
    """
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    return (
        "<!DOCTYPE html>"
        '<html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{safe_title} — TravelAI</title>"
        '<script src="https://cdn.tailwindcss.com"></script></head>'
        '<body class="bg-gray-50 min-h-screen flex items-center justify-center">'
        '<div class="text-center px-6" role="alert" aria-live="assertive">'
        '  <span class="text-6xl mb-6 block" aria-hidden="true">🌍</span>'
        f'  <h1 class="text-3xl font-bold text-gray-900 mb-3">{safe_title}</h1>'
        f'  <p class="text-gray-600 mb-8 max-w-md mx-auto">{safe_message}</p>'
        '  <a href="/" class="inline-block bg-blue-500 hover:bg-blue-700'
        " text-white font-semibold py-3 px-8 rounded-xl"
        ' transition-colors focus:ring-4 focus:ring-blue-300">'
        "    ← Back to Home"
        "  </a>"
        "</div></body></html>"
    )


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(ValidationError)
async def validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse | HTMLResponse:
    """Return clean validation errors without exposing internals."""
    if _is_html_request(request):
        return HTMLResponse(
            content=_error_html(
                "Invalid input",
                "Please check your form fields and try again.",
            ),
            status_code=422,
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse | HTMLResponse:
    """Friendly HTML error pages for browser requests."""
    if _is_html_request(request):
        messages = {
            400: ("Bad Request", str(exc.detail)),
            404: ("Page Not Found", "The page you're looking for doesn't exist."),
            429: ("Too Many Requests", "Please slow down and try again in a minute."),
            500: ("Something Went Wrong", "We encountered an issue. Please try again."),
        }
        title, desc = messages.get(exc.status_code, ("Error", str(exc.detail)))
        return HTMLResponse(
            content=_error_html(title, desc), status_code=exc.status_code
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse | HTMLResponse:
    """Catch-all: never show raw tracebacks to users."""
    logger.exception("Unhandled error: %s", exc)
    if _is_html_request(request):
        return HTMLResponse(
            content=_error_html(
                "Something Went Wrong",
                "We encountered an unexpected issue. Please try again later.",
            ),
            status_code=500,
        )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    """Health check endpoint for Cloud Run readiness probes.

    Returns:
        JSON object with service status and version.
    """
    return {"status": "ok", "version": "1.0.0"}
