"""
FastAPI Application Entry Point for QA Gate API.

Provides:
- Application factory create_app()
- CORS middleware for React / Next.js / dev frontend integration
- Top-level app instance for ASGI servers (Uvicorn)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import load_dotenv_if_present


def create_app() -> FastAPI:
    """Construct and configure the QA Gate FastAPI application."""
    load_dotenv_if_present()
    application = FastAPI(
        title="Deterministic QA Gate API",
        version="1.0.0",
        description=(
            "Clean UI/API boundary around the deterministic QA Gate pipeline. "
            "Exposes structured evaluation results for judge-facing UIs, React/Next.js "
            "frontends, and debug consoles without embedding business logic in the web layer."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Enable CORS for developer UI and future React / Next.js frontends
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach API routes
    application.include_router(router)

    return application


# Top-level ASGI instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.app:app", host="0.0.0.0", port=8000, reload=True)
