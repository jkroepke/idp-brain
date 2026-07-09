"""TOML extraction."""

from __future__ import annotations

import tomllib

from idp_brain.ingestion.extractors.base import (
    ArtifactExtractionContext,
    ExtractionResult,
    decode_utf8,
    make_result,
    result_with_parse_error,
)
from idp_brain.ingestion.extractors.structured import iter_structured_candidates


class TomlExtractor:
    name = "builtin-toml"
    version = "1"
    supported_artifact_roles = frozenset({"schema", "example", "unknown"})

    def extract(
        self,
        artifact: ArtifactExtractionContext,
        stream: bytes,
    ) -> ExtractionResult:
        text, diagnostics = decode_utf8(self.name, artifact, stream)
        try:
            parsed = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            return result_with_parse_error(
                extractor_name=self.name,
                extractor_version=self.version,
                artifact=artifact,
                code="toml_parse_error",
                error=exc,
            )
        return make_result(
            extractor_name=self.name,
            extractor_version=self.version,
            artifact=artifact,
            candidates=iter_structured_candidates(
                parsed,
                locator_prefix=artifact.logical_locator,
            ),
            diagnostics=diagnostics,
        )
