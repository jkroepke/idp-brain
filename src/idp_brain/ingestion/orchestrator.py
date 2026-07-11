"""Public validation-only ingestion orchestration boundary."""

from idp_brain.ingestion.pipeline import IngestionRunResult, run_ingestion

__all__ = ["IngestionRunResult", "run_ingestion"]
