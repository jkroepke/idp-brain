"""Fetcher interfaces for ingestion source snapshots."""

from __future__ import annotations

from typing import Protocol

from idp_brain.config.models import SourceConfig
from idp_brain.ingestion.source_snapshot import SourceSnapshot
from idp_brain.models import IngestionRun


class SourceFetcher(Protocol):
    """Fetch safe source metadata without persisting raw content."""

    def fetch(self, source: SourceConfig, run: IngestionRun) -> SourceSnapshot:
        """Return a deterministic metadata snapshot for a source."""
