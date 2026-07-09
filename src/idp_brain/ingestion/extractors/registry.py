"""Configuration-driven extractor selection."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath

from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.extractors.base import ArtifactExtractionContext, Extractor
from idp_brain.ingestion.extractors.html import HtmlExtractor
from idp_brain.ingestion.extractors.json import JsonExtractor
from idp_brain.ingestion.extractors.json_schema import JsonSchemaExtractor
from idp_brain.ingestion.extractors.markdown import MarkdownExtractor
from idp_brain.ingestion.extractors.openapi import OpenApiExtractor
from idp_brain.ingestion.extractors.source_code import SourceCodeExtractor
from idp_brain.ingestion.extractors.text import TextExtractor
from idp_brain.ingestion.extractors.toml import TomlExtractor
from idp_brain.ingestion.extractors.yaml import YamlExtractor


class ExtractorRegistry:
    """Select built-in extractors from artifact role, path, and profile config."""

    def __init__(
        self,
        profiles: Iterable[ExtractorProfileConfig] = (),
        extractors: Iterable[Extractor] | None = None,
    ) -> None:
        self._profiles = {profile.profile_id: profile for profile in profiles}
        self._extractors = tuple(extractors or _default_extractors())

    def select(self, artifact: ArtifactExtractionContext) -> Extractor:
        profile = self._profiles.get(artifact.extractor_profile or "")
        if profile is not None:
            return self._select_from_profile(artifact, profile, seen=set())
        return self._select_by_role_and_path(artifact)

    def _select_from_profile(
        self,
        artifact: ArtifactExtractionContext,
        profile: ExtractorProfileConfig,
        seen: set[str],
    ) -> Extractor:
        if profile.profile_id in seen:
            raise LookupError(f"cyclic extractor fallback: {profile.profile_id}")
        seen.add(profile.profile_id)
        if profile.enabled:
            for tool_id in _enabled_tool_ids(profile):
                extractor = self._select_from_tool(artifact, tool_id)
                if extractor is not None:
                    return extractor
        if profile.fallback_profile is not None:
            fallback = self._profiles.get(profile.fallback_profile)
            if fallback is not None:
                return self._select_from_profile(artifact, fallback, seen)
        raise LookupError(
            "no enabled extractor tool for profile "
            f"{profile.profile_id!r} and artifact {artifact.path!r}"
        )

    def _select_from_tool(
        self,
        artifact: ArtifactExtractionContext,
        tool_id: str,
    ) -> Extractor | None:
        suffix = PurePosixPath(artifact.path).suffix.lower()
        if tool_id == "builtin-markdown-html":
            if suffix in {".md", ".mdx"}:
                return _by_type(self._extractors, MarkdownExtractor)
            if suffix in {".html", ".htm"}:
                return _by_type(self._extractors, HtmlExtractor)
            return None
        if tool_id == "builtin-source-code-splitter":
            if artifact.artifact_role == "source_code":
                return _by_type(self._extractors, SourceCodeExtractor)
            return None
        if tool_id == "tree-sitter":
            if artifact.artifact_role == "source_code":
                return _by_type(self._extractors, SourceCodeExtractor)
            return None
        if tool_id == "builtin-structured-files":
            if artifact.artifact_role == "json_schema":
                return _by_type(self._extractors, JsonSchemaExtractor)
            if suffix == ".json":
                return _by_type(self._extractors, JsonExtractor)
            if suffix in {".yaml", ".yml"}:
                return _by_type(self._extractors, YamlExtractor)
            if suffix == ".toml":
                return _by_type(self._extractors, TomlExtractor)
            return None
        if tool_id == "builtin-openapi-parser":
            if artifact.artifact_role == "openapi_spec":
                return _by_type(self._extractors, OpenApiExtractor)
            return None
        if tool_id == "builtin-text":
            return _by_type(self._extractors, TextExtractor)
        if tool_id == "jsonschema":
            if artifact.artifact_role == "json_schema":
                return _by_type(self._extractors, JsonSchemaExtractor)
            return None
        return None

    def _select_by_role_and_path(
        self, artifact: ArtifactExtractionContext
    ) -> Extractor:
        if artifact.artifact_role == "openapi_spec":
            return _by_type(self._extractors, OpenApiExtractor)
        if artifact.artifact_role == "json_schema":
            return _by_type(self._extractors, JsonSchemaExtractor)
        if artifact.artifact_role == "source_code":
            return _by_type(self._extractors, SourceCodeExtractor)
        suffix = PurePosixPath(artifact.path).suffix.lower()
        if suffix in {".md", ".mdx"}:
            return _by_type(self._extractors, MarkdownExtractor)
        if suffix in {".html", ".htm"}:
            return _by_type(self._extractors, HtmlExtractor)
        if suffix == ".json":
            return _by_type(self._extractors, JsonExtractor)
        if suffix in {".yaml", ".yml"}:
            return _by_type(self._extractors, YamlExtractor)
        if suffix == ".toml":
            return _by_type(self._extractors, TomlExtractor)
        return _by_type(self._extractors, TextExtractor)


def _default_extractors() -> tuple[Extractor, ...]:
    return (
        MarkdownExtractor(),
        HtmlExtractor(),
        JsonExtractor(),
        YamlExtractor(),
        TomlExtractor(),
        TextExtractor(),
        SourceCodeExtractor(),
        OpenApiExtractor(),
        JsonSchemaExtractor(),
    )


def _by_type[TExtractor: Extractor](
    extractors: tuple[Extractor, ...],
    extractor_type: type[TExtractor],
) -> TExtractor:
    for extractor in extractors:
        if isinstance(extractor, extractor_type):
            return extractor
    raise LookupError(f"extractor is not registered: {extractor_type.__name__}")


def _enabled_tool_ids(profile: ExtractorProfileConfig) -> tuple[str, ...]:
    return tuple(tool.tool_id for tool in profile.tools if tool.enabled)
