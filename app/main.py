"""Main FastAPI application for HN GitHub Agents."""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models.responses import ErrorResponse
from .routers import analysis, chat, system
from .services import AgentManager
from .services.history_service import HistoryService, build_default_history_service
from .services.memory_service import MemoryService, build_default_memory_service
from .utils import get_logger, settings, setup_logging

# Set up logging
setup_logging()
logger = get_logger(__name__)

# Global services
agent_manager: AgentManager = AgentManager()
history_service: HistoryService = build_default_history_service()
memory_service: MemoryService = build_default_memory_service()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Starting HN GitHub Agents application")
    try:
        await agent_manager.initialize()
        logger.info(
            f"Current configuration: HN stories limit={settings.hn_stories_limit}, web search limit={settings.web_search_limit}"
        )
        logger.info("Application startup completed")
        # A2A apps are now mounted via AgentManager's router
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        raise

    yield

    logger.info("Shutting down HN GitHub Agents application")
    try:
        await agent_manager.shutdown()
        logger.info("Application shutdown completed")
    except Exception as e:
        logger.error(f"Error during application shutdown: {e}", exc_info=True)


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description=settings.description,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
cors_origins = ["*"]
if settings.environment.lower() == "production":
    if settings.allowed_origins:
        cors_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    else:
        cors_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for the UI
static_dir_path = Path(__file__).resolve().parent.parent / "static"
if static_dir_path.is_dir():
    app.mount("/static", StaticFiles(directory=static_dir_path), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    message = "An internal server error occurred" if settings.environment.lower() == "production" else str(exc)
    error_response = ErrorResponse(
        error="internal_server_error",
        message=message,
        timestamp=datetime.utcnow(),
    )
    return JSONResponse(status_code=500, content=error_response.dict())


# Include routers
app.include_router(system.router)
app.include_router(chat.router)
app.include_router(analysis.router)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        log_level=settings.log_level.lower(),
        reload=(settings.environment == "development"),
    )
