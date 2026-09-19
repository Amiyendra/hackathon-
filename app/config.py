"""Application configuration module."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


def load_dotenv_if_present(env_path: Optional[Path] = None) -> None:
    """
    Securely load environment variables from .env file into os.environ if present.
    Never prints or logs values.
    """
    path = env_path or (Path(__file__).resolve().parent.parent / ".env")
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        # Silently pass to avoid breaking if file unreadable
        pass


# Load .env on configuration import
load_dotenv_if_present()


class AppConfig(BaseModel):
    """Core application settings for QA Gate."""
    app_name: str = "Canonical QA Gate"
    version: str = "0.1.0"
    current_phase: str = "Phase 1: Foundation + Canonical Transcript"
    default_id_prefix: str = "utt_"
    default_id_padding: int = 3
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"


config = AppConfig()
