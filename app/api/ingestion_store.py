"""
Thread-safe in-memory session store for ingested transcripts.

Maintains canonical transcripts and extracted metadata across API requests.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional
import uuid

from app.models import CanonicalTranscript


@dataclass
class IngestionRecord:
    """Represents a validated and stored transcript ingestion session."""
    ingestion_id: str
    canonical_transcript: CanonicalTranscript
    raw_data: Optional[Dict[str, Any]]
    lead_id: Optional[str]
    retailer: Optional[str]
    call_date: Optional[str]
    created_at: datetime


class IngestionStore:
    """Thread-safe in-memory store for transcript ingestion sessions."""

    def __init__(self, max_records: int = 1000):
        self._lock = threading.Lock()
        self._store: Dict[str, IngestionRecord] = {}
        self.max_records = max_records

    def save(
        self,
        canonical_transcript: CanonicalTranscript,
        raw_data: Optional[Dict[str, Any]] = None,
        lead_id: Optional[str] = None,
        retailer: Optional[str] = None,
        call_date: Optional[str] = None,
    ) -> IngestionRecord:
        """Create and store a new ingestion record."""
        ingestion_id = f"ingest_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        record = IngestionRecord(
            ingestion_id=ingestion_id,
            canonical_transcript=canonical_transcript,
            raw_data=raw_data,
            lead_id=lead_id,
            retailer=retailer,
            call_date=call_date,
            created_at=now,
        )

        with self._lock:
            # Evict oldest if capacity exceeded
            if len(self._store) >= self.max_records:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[ingestion_id] = record

        return record

    def get(self, ingestion_id: str) -> Optional[IngestionRecord]:
        """Retrieve an ingestion record by ID."""
        with self._lock:
            return self._store.get(ingestion_id)

    def list_ids(self) -> List[str]:
        """List all active ingestion IDs."""
        with self._lock:
            return list(self._store.keys())

    def clear(self) -> None:
        """Clear all records (useful for test isolation)."""
        with self._lock:
            self._store.clear()


# Global singleton instance for API usage
ingestion_store = IngestionStore()
