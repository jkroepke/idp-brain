"""OpenAPI extraction."""

from __future__ import annotations

import json

import yaml
from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

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

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}


class OpenApiExtractor:
    name = "builtin-openapi"
    version = "1"
    supported_artifact_roles = frozenset({"openapi_spec"})

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
                code="openapi_parse_error",
                error=exc,
            )
        validation_diagnostics: list[ExtractionDiagnostic] = []
        try:
            validate(parsed)
        except OpenAPIValidationError as exc:
            validation_diagnostics.append(
                ExtractionDiagnostic(
                    severity="error",
                    code="openapi_validation_error",
                    message=getattr(exc, "message", str(exc)),
                    locator=artifact.logical_locator,
                )
            )
        candidates = list(
            iter_structured_candidates(parsed, locator_prefix=artifact.logical_locator)
        )
        candidates.extend(_operation_candidates(artifact, parsed))
        candidates.extend(_schema_candidates(artifact, parsed))
        return make_result(
            extractor_name=self.name,
            extractor_version=self.version,
            artifact=artifact,
            candidates=candidates,
            diagnostics=(*diagnostics, *validation_diagnostics),
        )


def _operation_candidates(
    artifact: ArtifactExtractionContext,
    parsed: object,
) -> list[ExtractionCandidate]:
    if not isinstance(parsed, dict) or not isinstance(parsed.get("paths"), dict):
        return []
    candidates: list[ExtractionCandidate] = []
    for path, methods in sorted(parsed["paths"].items()):
        if not isinstance(path, str) or not isinstance(methods, dict):
            continue
        for method, operation in sorted(methods.items()):
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            summary = operation.get("summary") or operation.get("description")
            metadata = (
                {"operation_id": operation_id} if isinstance(operation_id, str) else {}
            )
            candidates.append(
                ExtractionCandidate(
                    candidate_type="endpoint",
                    text=summary if isinstance(summary, str) else None,
                    locator=f"{artifact.logical_locator}#/paths/{path}/{method}",
                    key_path=("paths", path, method),
                    endpoint_path=f"{method.upper()} {path}",
                    metadata=metadata,
                )
            )
    return candidates


def _schema_candidates(
    artifact: ArtifactExtractionContext,
    parsed: object,
) -> list[ExtractionCandidate]:
    if not isinstance(parsed, dict):
        return []
    schemas = parsed.get("components", {})
    if isinstance(schemas, dict):
        schemas = schemas.get("schemas", {})
    if not isinstance(schemas, dict):
        return []
    return [
        ExtractionCandidate(
            candidate_type="schema",
            text=value.get("description") if isinstance(value, dict) else None,
            locator=f"{artifact.logical_locator}#/components/schemas/{name}",
            schema_path=("components", "schemas", str(name)),
        )
        for name, value in sorted(schemas.items())
    ]
