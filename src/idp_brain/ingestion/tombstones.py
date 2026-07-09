"""Safe tombstone reason constants for incremental ingestion."""

from __future__ import annotations

ARTIFACT_REMOVED_FROM_SOURCE = "removed_from_current_source_snapshot"
CHUNK_REMOVED_FROM_SOURCE = "removed_from_current_sanitized_snapshot"
SUPERSEDED_BY_NEW_VERSION = "superseded_by_new_source_version"
