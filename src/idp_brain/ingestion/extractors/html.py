"""HTML extraction using BeautifulSoup."""

from __future__ import annotations

from bs4 import BeautifulSoup
from bs4.element import Tag

from idp_brain.ingestion.extractors.base import (
    ArtifactExtractionContext,
    ExtractionCandidate,
    ExtractionResult,
    LineRange,
    decode_utf8,
    make_result,
)


class HtmlExtractor:
    name = "builtin-html"
    version = "1"
    supported_artifact_roles = frozenset({"documentation", "example"})

    def extract(
        self,
        artifact: ArtifactExtractionContext,
        stream: bytes,
    ) -> ExtractionResult:
        text, diagnostics = decode_utf8(self.name, artifact, stream)
        soup = BeautifulSoup(text, "lxml")
        headings: list[tuple[int, str]] = []
        candidates: list[ExtractionCandidate] = []
        for element in soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "code", "table"]
        ):
            if not isinstance(element, Tag):
                continue
            name = element.name or ""
            line_range = _line_range(element)
            locator = _locator(artifact, element, line_range)
            if name.startswith("h") and len(name) == 2:
                level = int(name.removeprefix("h"))
                title = element.get_text(" ", strip=True)
                headings = [(lvl, val) for lvl, val in headings if lvl < level]
                headings.append((level, title))
                candidates.append(
                    ExtractionCandidate(
                        candidate_type="heading",
                        text=title,
                        locator=locator,
                        line_range=line_range,
                        heading_path=tuple(value for _, value in headings),
                        metadata={"level": level, "anchor": element.get("id")},
                    )
                )
            elif name == "table":
                candidates.append(
                    ExtractionCandidate(
                        candidate_type="table",
                        text=None,
                        locator=locator,
                        line_range=line_range,
                        heading_path=tuple(value for _, value in headings),
                    )
                )
            elif name in {"pre", "code"}:
                candidates.append(
                    ExtractionCandidate(
                        candidate_type="code_block",
                        text=element.get_text("\n", strip=False),
                        locator=locator,
                        line_range=line_range,
                        heading_path=tuple(value for _, value in headings),
                    )
                )
            elif name == "p":
                candidates.append(
                    ExtractionCandidate(
                        candidate_type="section",
                        text=element.get_text(" ", strip=True),
                        locator=locator,
                        line_range=line_range,
                        heading_path=tuple(value for _, value in headings),
                    )
                )
        return make_result(
            extractor_name=self.name,
            extractor_version=self.version,
            artifact=artifact,
            candidates=candidates,
            diagnostics=diagnostics,
        )


def _line_range(element: Tag) -> LineRange | None:
    source_line = getattr(element, "sourceline", None)
    if not isinstance(source_line, int):
        return None
    return LineRange(source_line, source_line)


def _locator(
    artifact: ArtifactExtractionContext,
    element: Tag,
    line_range: LineRange | None,
) -> str:
    anchor = element.get("id")
    if isinstance(anchor, str) and anchor:
        return f"{artifact.logical_locator}#{anchor}"
    if line_range is not None:
        return f"{artifact.logical_locator}:L{line_range.start}"
    return f"{artifact.logical_locator}:{element.name}"
