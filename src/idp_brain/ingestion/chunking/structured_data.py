"""Structure-aware chunking for JSON, YAML, TOML, OpenAPI, and schemas."""

from __future__ import annotations

from idp_brain.ingestion.chunking.base import (
    ChunkingResult,
    ChunkingSettings,
    build_chunks_for_candidate,
)
from idp_brain.ingestion.redaction_stage import SanitizedExtractionCandidate


class StructuredDataChunker:
    """Preserve path metadata for structured scalar and schema candidates."""

    profile = "structured-data-v1"

    def __init__(self, settings: ChunkingSettings | None = None) -> None:
        self._settings = settings or ChunkingSettings()

    def chunk(
        self,
        candidate: SanitizedExtractionCandidate,
        *,
        extraction_id: str | None = None,
    ) -> ChunkingResult:
        original = candidate.original
        structure_path = _structure_path(candidate)
        metadata: dict[str, object] = {}
        if original.key_path:
            metadata["json_pointer"] = "/" + "/".join(
                part.replace("~", "~0").replace("/", "~1") for part in original.key_path
            )
            metadata["dotted_key"] = ".".join(original.key_path)
        if original.schema_path:
            metadata["schema_path"] = list(original.schema_path)
        if original.endpoint_path is not None:
            metadata["endpoint_path"] = original.endpoint_path
        for key in (
            "operation_id",
            "schema_name",
            "required",
            "enum",
            "constraints",
            "examples",
            "value_type",
        ):
            if key in original.metadata:
                metadata[key] = original.metadata[key]
        return build_chunks_for_candidate(
            candidate=candidate,
            chunk_kind=_structured_kind(original.candidate_type),
            chunker_profile=self.profile,
            settings=self._settings,
            extraction_id=extraction_id,
            structure_path=structure_path,
            metadata=metadata,
        )


def _structure_path(candidate: SanitizedExtractionCandidate) -> tuple[str, ...]:
    original = candidate.original
    if original.endpoint_path is not None:
        path: tuple[str, ...] = ("openapi", original.endpoint_path)
        operation_id = original.metadata.get("operation_id")
        if isinstance(operation_id, str):
            path = (*path, operation_id)
        return (*path, original.candidate_type, original.locator)
    if original.schema_path:
        return ("schema", *original.schema_path, original.candidate_type)
    if original.key_path:
        return ("structured", *original.key_path, original.candidate_type)
    return ("structured", original.candidate_type, original.locator)


def _structured_kind(candidate_type: str) -> str:
    if candidate_type in {"endpoint", "schema", "schema_path"}:
        return candidate_type
    if candidate_type in {"scalar", "object", "array"}:
        return f"structured_{candidate_type}"
    return "structured_value"
