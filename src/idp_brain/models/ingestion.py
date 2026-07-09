"""Ingestion lifecycle model constants."""

from __future__ import annotations

from enum import StrEnum


class IngestionRunStatus(StrEnum):
    """Explicit statuses for a local ingestion attempt."""

    started = "started"
    fetching = "fetching"
    discovering = "discovering"
    extracting = "extracting"
    redacting = "redacting"
    chunking = "chunking"
    persisting = "persisting"
    completed = "completed"
    failed = "failed"


INGESTION_COUNTER_KEYS: tuple[str, ...] = (
    "fetched_artifacts",
    "discovered_artifacts",
    "extracted_artifacts",
    "redacted_candidates",
    "persisted_sanitized_chunks",
    "added_artifacts",
    "changed_artifacts",
    "unchanged_artifacts",
    "tombstoned_artifacts",
    "added_chunks",
    "changed_chunks",
    "unchanged_chunks",
    "tombstoned_chunks",
    "skipped_generated_files",
    "skipped_vendored_files",
    "failed_artifacts",
    "tombstoned_records",
)


def empty_ingestion_counters() -> dict[str, int]:
    """Return deterministic zeroed counters for a newly started run."""

    return {key: 0 for key in INGESTION_COUNTER_KEYS}
