"""
API Layer for QA Gate Backend.

Exposes the deterministic pipeline via FastAPI to decouple the core QA engine
from frontend presentations (developer debug UI, React/Next.js).
"""

from app.api.app import app, create_app
from app.api.models import HealthResponse, QARunRequest, ScenarioInfo

__all__ = [
    "app",
    "create_app",
    "QARunRequest",
    "HealthResponse",
    "ScenarioInfo",
]
