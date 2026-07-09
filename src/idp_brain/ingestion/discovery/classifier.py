"""Artifact discovery classification and filtering."""

from __future__ import annotations

import mimetypes
from dataclasses import replace
from pathlib import Path, PurePosixPath

from idp_brain.config import load_extractors_config
from idp_brain.config.models import ExtractorProfileConfig, SourceConfig
from idp_brain.ingestion.discovery.linguist import LinguistAdapter
from idp_brain.ingestion.discovery.path_rules import (
    first_matching_pattern,
    matches_includes,
    matches_pattern,
    normalize_relative_path,
)
from idp_brain.ingestion.source_snapshot import (
    ArtifactCandidate,
    SkippedArtifact,
    SourceSnapshot,
)

DISCOVERY_RULE_VERSION = "artifact-discovery-v1"


class ArtifactDiscoveryService:
    """Classify fetched artifacts and apply discovery-time inclusion rules."""

    def __init__(
        self,
        *,
        config_path: Path,
        linguist: LinguistAdapter | None = None,
    ) -> None:
        self._extractor_profiles = _load_extractor_profiles(config_path)
        self._linguist = linguist or LinguistAdapter()

    def discover(self, snapshot: SourceSnapshot) -> SourceSnapshot:
        """Return a snapshot containing only extraction-eligible artifacts."""

        discovered: list[ArtifactCandidate] = []
        skipped: list[SkippedArtifact] = [*snapshot.skipped]
        for artifact in snapshot.artifacts:
            classified = self._classify_artifact(snapshot.source, artifact)
            skip = _skip_decision(snapshot.source, classified)
            if skip is not None:
                skipped.append(skip)
                continue
            discovered.append(classified)

        return replace(
            snapshot,
            artifacts=tuple(sorted(discovered, key=lambda item: item.path)),
            skipped=tuple(skipped),
        )

    def _classify_artifact(
        self,
        source: SourceConfig,
        artifact: ArtifactCandidate,
    ) -> ArtifactCandidate:
        path = normalize_relative_path(artifact.path)
        linguist_classification = self._linguist.classify_path(path)
        mime_type = artifact.mime_type or mimetypes.guess_type(path)[0]
        artifact_role = _artifact_role(path, linguist_classification.language)
        profile = self._select_profile(source, path, artifact_role)
        is_generated = linguist_classification.generated
        is_vendored = linguist_classification.vendored
        override_reason = _override_reason(
            source=source,
            profile=profile,
            path=path,
            generated=is_generated,
            vendored=is_vendored,
        )
        return replace(
            artifact,
            path=path,
            artifact_type=_artifact_type(path, mime_type),
            artifact_role=artifact_role,
            mime_type=mime_type,
            language=linguist_classification.language or artifact.language,
            corpus_eligibility_label=source.corpus_eligibility,
            extractor_profile=profile.profile_id,
            included=True,
            skipped=False,
            skip_reason=None,
            generated=is_generated,
            vendored=is_vendored,
            override_reason=override_reason,
            discovery_rule_version=DISCOVERY_RULE_VERSION,
        )

    def _select_profile(
        self,
        source: SourceConfig,
        path: str,
        artifact_role: str,
    ) -> ExtractorProfileConfig:
        explicit_profile = self._extractor_profiles.get(source.extractor_profile)
        if explicit_profile is None:
            raise ValueError("source references unknown extractor profile")

        preferred_family = _preferred_extractor_family(artifact_role)
        if preferred_family is not None:
            for profile in self._extractor_profiles.values():
                if not profile.enabled or profile.family != preferred_family:
                    continue
                if any(
                    matches_pattern(path, pattern) for pattern in profile.file_patterns
                ):
                    return profile

        for profile in self._extractor_profiles.values():
            if not profile.enabled:
                continue
            if any(matches_pattern(path, pattern) for pattern in profile.file_patterns):
                return profile
        return explicit_profile


def _load_extractor_profiles(config_path: Path) -> dict[str, ExtractorProfileConfig]:
    candidates = [
        config_path.parent / "extractors.yaml",
        Path("config/extractors.yaml"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            config = load_extractors_config(candidate)
            return {profile.profile_id: profile for profile in config.profiles}
    raise FileNotFoundError("extractors.yaml is required for artifact discovery")


def _skip_decision(
    source: SourceConfig,
    artifact: ArtifactCandidate,
) -> SkippedArtifact | None:
    excluded_pattern = first_matching_pattern(artifact.path, source.exclude_paths)
    if excluded_pattern is not None and not _has_exclude_override(
        source,
        artifact.path,
    ):
        return _skipped_artifact(
            artifact,
            reason="excluded_by_glob",
            pattern=excluded_pattern,
        )
    if not matches_includes(artifact.path, source.include_paths):
        return _skipped_artifact(artifact, reason="not_included_by_glob")
    if artifact.generated and artifact.override_reason is None:
        return _skipped_artifact(artifact, reason="generated_file")
    if artifact.vendored and artifact.override_reason is None:
        return _skipped_artifact(artifact, reason="vendored_file")
    return None


def _skipped_artifact(
    artifact: ArtifactCandidate,
    *,
    reason: str,
    pattern: str | None = None,
) -> SkippedArtifact:
    return SkippedArtifact(
        locator=artifact.path,
        reason=reason,
        pattern=pattern,
        included=False,
        skipped=True,
        generated=artifact.generated,
        vendored=artifact.vendored,
        override_reason=artifact.override_reason,
        discovery_rule_version=DISCOVERY_RULE_VERSION,
    )


def _override_reason(
    *,
    source: SourceConfig,
    profile: ExtractorProfileConfig,
    path: str,
    generated: bool,
    vendored: bool,
) -> str | None:
    overridden_by_generated_or_vendored = (
        generated and (source.include_generated or profile.include_generated)
    ) or (vendored and (source.include_vendored or profile.include_vendored))
    overridden_by_exclude = _has_exclude_override(source, path)
    if not overridden_by_generated_or_vendored and not overridden_by_exclude:
        return None
    override_kind = _override_kind(generated, vendored, overridden_by_exclude)
    return (
        source.discovery_override_reason or f"source_or_profile_allows_{override_kind}"
    )


def _has_exclude_override(source: SourceConfig, path: str) -> bool:
    if source.discovery_override_reason is None:
        return False
    if first_matching_pattern(path, source.exclude_paths) is None:
        return False
    return first_matching_pattern(path, source.override_exclude_paths) is not None


def _override_kind(
    generated: bool,
    vendored: bool,
    excluded: bool,
) -> str:
    if excluded:
        return "excluded"
    if generated:
        return "generated"
    if vendored:
        return "vendored"
    return "artifact"


def _preferred_extractor_family(artifact_role: str) -> str | None:
    if artifact_role in {"documentation", "changelog", "license", "example"}:
        return "docs"
    if artifact_role == "source_code":
        return "code"
    if artifact_role == "openapi_spec":
        return "api_specs"
    if artifact_role in {"schema", "json_schema"}:
        return "schemas"
    return None


def _artifact_type(path: str, mime_type: str | None) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {".md", ".markdown", ".mdx", ".html", ".htm", ".txt"}:
        return "document"
    if suffix in {".json", ".yaml", ".yml", ".toml", ".xml"}:
        return "structured_data"
    if suffix in {".py", ".js", ".ts", ".go", ".rs", ".java", ".sh", ".c", ".cpp"}:
        return "source_code"
    if mime_type is not None and mime_type.startswith("text/"):
        return "document"
    return "file"


def _artifact_role(path: str, language: str | None) -> str:
    posix_path = PurePosixPath(path)
    lowered_path = posix_path.as_posix().lower()
    name = posix_path.name.lower()
    suffix = posix_path.suffix.lower()
    if name.startswith("license") or name in {"copying", "notice"}:
        return "license"
    if name.startswith("changelog") or name in {"changes.md", "history.md"}:
        return "changelog"
    if "test" in {part.lower() for part in posix_path.parts} or name.startswith(
        "test_"
    ):
        return "test"
    if "example" in lowered_path or "examples/" in lowered_path:
        return "example"
    if "openapi" in lowered_path:
        return "openapi_spec"
    if suffix == ".json" and (
        name.endswith(".schema.json") or "schema" in lowered_path
    ):
        return "json_schema"
    if language in {
        "python",
        "javascript",
        "typescript",
        "go",
        "rust",
        "java",
        "c",
        "c++",
    }:
        return "source_code"
    if language in {"markdown", "mdx", "html", "text"}:
        return "documentation"
    if suffix in {".json", ".yaml", ".yml", ".toml", ".xml"}:
        return "schema"
    return "unknown"
