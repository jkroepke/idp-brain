"""Document-oriented sanitized chunking."""

from __future__ import annotations

from idp_brain.ingestion.chunking.base import (
    ChunkingResult,
    ChunkingSettings,
    build_chunks_for_candidate,
)
from idp_brain.ingestion.redaction_stage import SanitizedExtractionCandidate


class DocumentChunker:
    """Preserve heading, paragraph, list, table, and code-block context."""

    profile = "document-structure-v1"

    def __init__(self, settings: ChunkingSettings | None = None) -> None:
        self._settings = settings or ChunkingSettings()

    def chunk(
        self,
        candidate: SanitizedExtractionCandidate,
        *,
        extraction_id: str | None = None,
    ) -> ChunkingResult:
        original = candidate.original
        heading_path = original.heading_path
        chunk_kind = _document_kind(original.candidate_type)
        structure_path = (
            "document",
            *heading_path,
            original.candidate_type,
            original.locator,
        )
        metadata: dict[str, object] = {}
        anchor = original.metadata.get("anchor")
        if isinstance(anchor, str):
            metadata["anchor"] = anchor
        if original.language is not None and original.candidate_type == "code_block":
            metadata["code_language"] = original.language
        return build_chunks_for_candidate(
            candidate=candidate,
            chunk_kind=chunk_kind,
            chunker_profile=self.profile,
            settings=self._settings,
            extraction_id=extraction_id,
            structure_path=structure_path,
            heading_path=heading_path,
            language=original.language,
            metadata=metadata,
        )


def _document_kind(candidate_type: str) -> str:
    if candidate_type in {"heading", "section", "paragraph", "table", "code_block"}:
        return candidate_type
    return "document_block"
