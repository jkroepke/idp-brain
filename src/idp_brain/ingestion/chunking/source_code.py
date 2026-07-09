"""Source-code chunking using extractor symbol metadata."""

from __future__ import annotations

from idp_brain.ingestion.chunking.base import (
    ChunkingResult,
    ChunkingSettings,
    build_chunks_for_candidate,
)
from idp_brain.ingestion.redaction_stage import SanitizedExtractionCandidate


class SourceCodeChunker:
    """Preserve language, symbol path, signatures, imports, and parent context."""

    profile = "source-code-symbols-v1"

    def __init__(self, settings: ChunkingSettings | None = None) -> None:
        self._settings = settings or ChunkingSettings()

    def chunk(
        self,
        candidate: SanitizedExtractionCandidate,
        *,
        extraction_id: str | None = None,
    ) -> ChunkingResult:
        original = candidate.original
        symbol_path = original.symbol_path
        structure_path = (
            "source_code",
            original.language or "unknown",
            *(symbol_path or (original.locator,)),
            original.candidate_type,
        )
        metadata: dict[str, object] = {}
        if "imports" in original.metadata:
            metadata["imports"] = original.metadata["imports"]
        if "symbol_type" in original.metadata:
            metadata["symbol_type"] = original.metadata["symbol_type"]
        if len(symbol_path) > 1:
            metadata["parent_symbol_path"] = list(symbol_path[:-1])
        return build_chunks_for_candidate(
            candidate=candidate,
            chunk_kind=(
                "source_symbol"
                if original.candidate_type == "symbol"
                else "source_block"
            ),
            chunker_profile=self.profile,
            settings=self._settings,
            extraction_id=extraction_id,
            structure_path=structure_path,
            symbol_path=symbol_path,
            signature_text=original.signature_text,
            language=original.language,
            metadata=metadata,
        )
