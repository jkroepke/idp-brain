"""Markdown extraction using markdown-it-py tokens."""

from __future__ import annotations

from markdown_it import MarkdownIt

from idp_brain.ingestion.extractors.base import (
    ArtifactExtractionContext,
    ExtractionCandidate,
    ExtractionResult,
    LineRange,
    decode_utf8,
    make_result,
)


class MarkdownExtractor:
    name = "builtin-markdown"
    version = "1"
    supported_artifact_roles = frozenset({"documentation", "changelog", "example"})

    def __init__(self) -> None:
        self._parser = MarkdownIt("commonmark").enable("table")

    def extract(
        self,
        artifact: ArtifactExtractionContext,
        stream: bytes,
    ) -> ExtractionResult:
        text, diagnostics = decode_utf8(self.name, artifact, stream)
        tokens = self._parser.parse(text)
        headings: list[tuple[int, str]] = []
        candidates: list[ExtractionCandidate] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            next_token = tokens[index + 1] if index + 1 < len(tokens) else None
            if token.type == "heading_open" and next_token is not None:
                level = int(token.tag[1]) if token.tag.startswith("h") else 1
                title = next_token.content.strip()
                headings = [(lvl, val) for lvl, val in headings if lvl < level]
                headings.append((level, title))
                candidates.append(
                    ExtractionCandidate(
                        candidate_type="heading",
                        text=title,
                        locator=_locator(artifact, token.map),
                        line_range=LineRange.from_zero_based(token.map),
                        heading_path=tuple(value for _, value in headings),
                        metadata={"level": level, "anchor": _anchor(title)},
                    )
                )
            elif token.type == "paragraph_open" and next_token is not None:
                candidates.append(
                    ExtractionCandidate(
                        candidate_type="section",
                        text=next_token.content,
                        locator=_locator(artifact, token.map),
                        line_range=LineRange.from_zero_based(token.map),
                        heading_path=tuple(value for _, value in headings),
                    )
                )
            elif token.type == "fence":
                candidates.append(
                    ExtractionCandidate(
                        candidate_type="code_block",
                        text=token.content,
                        locator=_locator(artifact, token.map),
                        line_range=LineRange.from_zero_based(token.map),
                        heading_path=tuple(value for _, value in headings),
                        language=(token.info or "").split(maxsplit=1)[0] or None,
                    )
                )
            elif token.type == "table_open":
                candidates.append(
                    ExtractionCandidate(
                        candidate_type="table",
                        text=None,
                        locator=_locator(artifact, token.map),
                        line_range=LineRange.from_zero_based(token.map),
                        heading_path=tuple(value for _, value in headings),
                    )
                )
            index += 1
        return make_result(
            extractor_name=self.name,
            extractor_version=self.version,
            artifact=artifact,
            candidates=candidates,
            diagnostics=diagnostics,
        )


def _locator(artifact: ArtifactExtractionContext, line_map: list[int] | None) -> str:
    line_range = LineRange.from_zero_based(line_map)
    if line_range is None:
        return artifact.logical_locator
    return f"{artifact.logical_locator}:L{line_range.start}-L{line_range.end}"


def _anchor(title: str) -> str:
    return "-".join(part for part in title.lower().split() if part)
