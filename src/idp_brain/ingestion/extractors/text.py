"""Plain text extraction."""

from __future__ import annotations

from idp_brain.ingestion.extractors.base import (
    ArtifactExtractionContext,
    ExtractionCandidate,
    ExtractionResult,
    LineRange,
    decode_utf8,
    make_result,
)


class TextExtractor:
    name = "builtin-text"
    version = "1"
    supported_artifact_roles = frozenset({"documentation", "example", "unknown"})

    def extract(
        self,
        artifact: ArtifactExtractionContext,
        stream: bytes,
    ) -> ExtractionResult:
        text, diagnostics = decode_utf8(self.name, artifact, stream)
        candidates: list[ExtractionCandidate] = []
        block_lines: list[str] = []
        block_start: int | None = None
        for index, line in enumerate(text.splitlines(), start=1):
            if line.strip():
                if block_start is None:
                    block_start = index
                block_lines.append(line)
                continue
            if block_lines and block_start is not None:
                candidates.append(
                    _paragraph(artifact, block_start, index - 1, block_lines)
                )
            block_lines = []
            block_start = None
        if block_lines and block_start is not None:
            candidates.append(
                _paragraph(artifact, block_start, len(text.splitlines()), block_lines)
            )
        return make_result(
            extractor_name=self.name,
            extractor_version=self.version,
            artifact=artifact,
            candidates=candidates,
            diagnostics=diagnostics,
        )


def _paragraph(
    artifact: ArtifactExtractionContext,
    start: int,
    end: int,
    lines: list[str],
) -> ExtractionCandidate:
    return ExtractionCandidate(
        candidate_type="paragraph",
        text="\n".join(lines),
        locator=f"{artifact.logical_locator}:L{start}-L{end}",
        line_range=LineRange(start, end),
    )
