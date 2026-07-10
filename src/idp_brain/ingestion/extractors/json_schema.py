"""JSON Schema extraction."""

from __future__ import annotations

import json
from typing import cast

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from idp_brain.ingestion.extractors.base import (
    ArtifactExtractionContext,
    ExtractionCandidate,
    ExtractionDiagnostic,
    ExtractionResult,
    decode_utf8,
    make_result,
    result_with_parse_error,
)
from idp_brain.ingestion.extractors.structured import iter_structured_candidates


class JsonSchemaExtractor:
    name = "builtin-json-schema"
    version = "1"
    supported_artifact_roles = frozenset({"json_schema"})

    def extract(
        self,
        artifact: ArtifactExtractionContext,
        stream: bytes,
    ) -> ExtractionResult:
        text, diagnostics = decode_utf8(self.name, artifact, stream)
        try:
            parsed = (
                json.loads(text)
                if artifact.path.endswith(".json")
                else yaml.safe_load(text)
            )
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            return result_with_parse_error(
                extractor_name=self.name,
                extractor_version=self.version,
                artifact=artifact,
                code="json_schema_parse_error",
                error=exc,
            )
        validation_diagnostics: list[ExtractionDiagnostic] = []
        try:
            Draft202012Validator.check_schema(parsed)
        except SchemaError as exc:
            validation_diagnostics.append(
                ExtractionDiagnostic(
                    severity="error",
                    code="json_schema_validation_error",
                    message=exc.message,
                    locator=artifact.logical_locator,
                )
            )
        candidates = list(
            iter_structured_candidates(parsed, locator_prefix=artifact.logical_locator)
        )
        candidates.extend(_schema_property_candidates(artifact, parsed))
        return make_result(
            extractor_name=self.name,
            extractor_version=self.version,
            artifact=artifact,
            candidates=candidates,
            diagnostics=(*diagnostics, *validation_diagnostics),
        )


def _schema_property_candidates(
    artifact: ArtifactExtractionContext,
    parsed: object,
) -> list[ExtractionCandidate]:
    if not isinstance(parsed, dict):
        return []
    schema = cast(dict[str, object], parsed)
    candidates: list[ExtractionCandidate] = []
    definitions = schema.get("$defs")
    if isinstance(definitions, dict):
        for name, value in sorted(definitions.items()):
            candidates.append(_schema_candidate(artifact, ("$defs", str(name)), value))
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, value in sorted(properties.items()):
            candidates.append(
                _schema_candidate(artifact, ("properties", str(name)), value)
            )
    return candidates


def _schema_candidate(
    artifact: ArtifactExtractionContext,
    path: tuple[str, ...],
    value: object,
) -> ExtractionCandidate:
    text = None
    metadata: dict[str, object] = {}
    if isinstance(value, dict):
        schema = cast(dict[str, object], value)
        description = schema.get("description")
        if isinstance(description, str):
            text = description
        if "type" in schema:
            metadata["type"] = str(schema["type"])
        if "required" in schema:
            metadata["required"] = schema["required"]
        if "enum" in schema:
            enum = schema["enum"]
            metadata["enum_count"] = len(enum) if isinstance(enum, list) else 0
    return ExtractionCandidate(
        candidate_type="schema_path",
        text=text,
        locator=f"{artifact.logical_locator}#/" + "/".join(path),
        schema_path=path,
        metadata=metadata,
    )
