import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.config import settings
from app.routes import pages, api

app = FastAPI(
    title="Travel Planning & Experience Engine",
    description="AI-powered trip planner using Gemini, Google Maps, and more",
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


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Return clean validation errors."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "ok", "version": "1.0.0"}
