"""Selection pipeline for sanitized structure-aware chunking."""

from __future__ import annotations

from collections.abc import Iterable

from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.chunking.base import (
    ChunkingResult,
    ChunkingSettings,
    SanitizedChunk,
    SanitizedCitation,
)
from idp_brain.ingestion.chunking.documents import DocumentChunker
from idp_brain.ingestion.chunking.source_code import SourceCodeChunker
from idp_brain.ingestion.chunking.structured_data import StructuredDataChunker
from idp_brain.ingestion.redaction_stage import (
    SanitizedExtractionCandidate,
    SanitizedExtractionResult,
)


class ChunkingPipeline:
    """Chunk sanitized extraction results without fetching or indexing."""

    def __init__(self, profile: ExtractorProfileConfig | None = None) -> None:
        settings = ChunkingSettings.from_profile(profile)
        self._document_chunker = DocumentChunker(settings)
        self._structured_chunker = StructuredDataChunker(settings)
        self._source_code_chunker = SourceCodeChunker(settings)

    def chunk_result(
        self,
        result: SanitizedExtractionResult,
        *,
        extraction_id: str | None = None,
    ) -> ChunkingResult:
        chunk_results = (
            self._chunk_candidate(candidate, extraction_id=extraction_id)
            for candidate in result.candidates
        )
        return _merge(chunk_results)

    def _chunk_candidate(
        self,
        candidate: SanitizedExtractionCandidate,
        *,
        extraction_id: str | None,
    ) -> ChunkingResult:
        original = candidate.original
        if original.candidate_type in {"object", "array", "import"}:
            return ChunkingResult(chunks=(), citations=())
        if (
            original.key_path
            or original.schema_path
            or original.endpoint_path is not None
            or original.candidate_type
            in {"scalar", "endpoint", "schema", "schema_path"}
        ):
            return self._structured_chunker.chunk(
                candidate, extraction_id=extraction_id
            )
        if original.symbol_path or original.candidate_type == "symbol":
            return self._source_code_chunker.chunk(
                candidate, extraction_id=extraction_id
            )
        return self._document_chunker.chunk(candidate, extraction_id=extraction_id)


def _merge(results: Iterable[ChunkingResult]) -> ChunkingResult:
    chunks: list[SanitizedChunk] = []
    citations: list[SanitizedCitation] = []
    for result in results:
        chunks.extend(result.chunks)
        citations.extend(result.citations)
    return ChunkingResult(chunks=tuple(chunks), citations=tuple(citations))
