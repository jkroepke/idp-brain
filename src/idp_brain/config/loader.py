"""Local-only YAML configuration loader."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError

from idp_brain.config.errors import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigReferenceError,
    ConfigValidationError,
)
from idp_brain.config.models import (
    AccessConfig,
    ConfigBundle,
    ConfigModel,
    EvaluationConfig,
    ExtractorsConfig,
    MemoryConfig,
    ModelsConfig,
    RetrievalConfig,
    SecurityConfig,
    SourcesConfig,
)

REQUIRED_CONFIG_FILES: Mapping[str, str] = {
    "sources": "sources.yaml",
    "extractors": "extractors.yaml",
    "models": "models.yaml",
    "retrieval": "retrieval.yaml",
    "evaluation": "evaluation.yaml",
    "security": "security.yaml",
    "access": "access.yaml",
    "memory": "memory.yaml",
}


def load_config_dir(config_dir: Path) -> ConfigBundle:
    """Load and cross-validate all required YAML config files from a directory."""

    paths = {
        config_name: config_dir / filename
        for config_name, filename in REQUIRED_CONFIG_FILES.items()
    }
    missing_paths = [path for path in paths.values() if not path.is_file()]
    if missing_paths:
        raise ConfigFileNotFoundError(
            "required config files are missing",
            paths=missing_paths,
        )

    bundle = ConfigBundle(
        sources=load_sources_config(paths["sources"]),
        extractors=load_extractors_config(paths["extractors"]),
        models=load_models_config(paths["models"]),
        retrieval=load_retrieval_config(paths["retrieval"]),
        evaluation=load_evaluation_config(paths["evaluation"]),
        security=load_security_config(paths["security"]),
        access=load_access_config(paths["access"]),
        memory=load_memory_config(paths["memory"]),
    )
    _validate_cross_file_references(bundle, paths)
    return bundle


def load_sources_config(path: Path) -> SourcesConfig:
    """Load ``sources.yaml``."""

    return _load_typed_config(path, SourcesConfig)


def load_extractors_config(path: Path) -> ExtractorsConfig:
    """Load ``extractors.yaml``."""

    return _load_typed_config(path, ExtractorsConfig)


def load_models_config(path: Path) -> ModelsConfig:
    """Load ``models.yaml``."""

    return _load_typed_config(path, ModelsConfig)


def load_retrieval_config(path: Path) -> RetrievalConfig:
    """Load ``retrieval.yaml``."""

    return _load_typed_config(path, RetrievalConfig)


def load_evaluation_config(path: Path) -> EvaluationConfig:
    """Load ``evaluation.yaml``."""

    return _load_typed_config(path, EvaluationConfig)


def load_security_config(path: Path) -> SecurityConfig:
    """Load ``security.yaml``."""

    return _load_typed_config(path, SecurityConfig)


def load_access_config(path: Path) -> AccessConfig:
    """Load ``access.yaml``."""

    return _load_typed_config(path, AccessConfig)


def load_memory_config(path: Path) -> MemoryConfig:
    """Load ``memory.yaml``."""

    return _load_typed_config(path, MemoryConfig)


def _load_typed_config[TConfig: ConfigModel](
    path: Path,
    model_type: type[TConfig],
) -> TConfig:
    if not path.is_file():
        raise ConfigFileNotFoundError("required config file is missing", path=path)

    raw_data = _load_yaml_mapping(path)
    try:
        return model_type.model_validate(raw_data)
    except ValidationError as exc:
        raise ConfigValidationError(
            f"{path.name} failed validation: {exc}",
            path=path,
        ) from exc


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    try:
        raw_text = path.read_text(encoding="utf-8")
        loaded = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigParseError(
            f"{path.name} is not valid YAML: {exc}", path=path
        ) from exc
    except OSError as exc:
        raise ConfigParseError(
            f"{path.name} could not be read: {exc}", path=path
        ) from exc

    if loaded is None:
        raise ConfigParseError(f"{path.name} is empty", path=path)
    if not isinstance(loaded, dict):
        raise ConfigParseError(f"{path.name} must contain a YAML mapping", path=path)
    if not all(isinstance(key, str) for key in loaded):
        raise ConfigParseError(f"{path.name} mapping keys must be strings", path=path)

    return cast(dict[str, object], loaded)


def _validate_cross_file_references(
    bundle: ConfigBundle,
    paths: Mapping[str, Path],
) -> None:
    source_ids = [source.source_id for source in bundle.sources.sources]
    _raise_on_duplicates(source_ids, "source IDs", paths["sources"])

    extractor_ids = [profile.profile_id for profile in bundle.extractors.profiles]
    _raise_on_duplicates(extractor_ids, "extractor profiles", paths["extractors"])
    known_extractors = set(extractor_ids)
    for source in bundle.sources.sources:
        if source.extractor_profile not in known_extractors:
            raise ConfigReferenceError(
                "unknown extractor profile "
                f"{source.extractor_profile!r} referenced by source "
                f"{source.source_id!r}",
                path=paths["sources"],
            )
    for extractor_profile in bundle.extractors.profiles:
        if extractor_profile.fallback_profile is not None and (
            extractor_profile.fallback_profile not in known_extractors
        ):
            raise ConfigReferenceError(
                "unknown extractor fallback profile "
                f"{extractor_profile.fallback_profile!r} referenced by extractor "
                f"{extractor_profile.profile_id!r}",
                path=paths["extractors"],
            )

    embedding_ids = [profile.model_id for profile in bundle.models.embedding_profiles]
    reranker_ids = [profile.model_id for profile in bundle.models.reranker_profiles]
    generator_ids = [profile.model_id for profile in bundle.models.generator_profiles]
    _raise_on_duplicates(embedding_ids, "embedding model IDs", paths["models"])
    _raise_on_duplicates(reranker_ids, "reranker model IDs", paths["models"])
    _raise_on_duplicates(generator_ids, "generator model IDs", paths["models"])

    known_embeddings = set(embedding_ids)
    known_rerankers = set(reranker_ids)
    known_generators = set(generator_ids)
    known_models_by_purpose = {
        "embedding": known_embeddings,
        "reranker": known_rerankers,
        "generator": known_generators,
    }

    for route in bundle.models.provider_routes:
        known_models = known_models_by_purpose[route.purpose]
        if route.primary_model not in known_models:
            raise ConfigReferenceError(
                "unknown primary model "
                f"{route.primary_model!r} referenced by provider route "
                f"{route.route_id!r}",
                path=paths["models"],
            )
        for fallback_model in route.fallback_models:
            if fallback_model not in known_models:
                raise ConfigReferenceError(
                    "unknown fallback model "
                    f"{fallback_model!r} referenced by provider route "
                    f"{route.route_id!r}",
                    path=paths["models"],
                )

    for retrieval_profile in bundle.retrieval.query_profiles:
        if retrieval_profile.embedding_model not in known_embeddings:
            raise ConfigReferenceError(
                "unknown embedding model "
                f"{retrieval_profile.embedding_model!r} referenced by retrieval "
                f"profile {retrieval_profile.profile_id!r}",
                path=paths["retrieval"],
            )
        if (
            retrieval_profile.reranker is not None
            and retrieval_profile.reranker not in known_rerankers
        ):
            raise ConfigReferenceError(
                "unknown reranker "
                f"{retrieval_profile.reranker!r} referenced by retrieval profile "
                f"{retrieval_profile.profile_id!r}",
                path=paths["retrieval"],
            )

    for model_id in bundle.evaluation.embedding_fine_tuning.candidate_models:
        if model_id not in known_embeddings:
            raise ConfigReferenceError(
                f"unknown embedding fine-tuning candidate model {model_id!r}",
                path=paths["evaluation"],
            )

    visibility_labels = [label.label for label in bundle.access.visibility_labels]
    sensitivity_labels = [label.label for label in bundle.access.sensitivity_labels]
    license_labels = [label.label for label in bundle.access.license_policy_labels]
    _raise_on_duplicates(visibility_labels, "visibility labels", paths["access"])
    _raise_on_duplicates(sensitivity_labels, "sensitivity labels", paths["access"])
    _raise_on_duplicates(license_labels, "license policy labels", paths["access"])
    known_visibility = set(visibility_labels)
    known_sensitivity = set(sensitivity_labels)
    known_licenses = set(license_labels)

    for source in bundle.sources.sources:
        _require_known_label(
            source.visibility_label,
            known_visibility,
            "visibility label",
            paths["sources"],
        )
        _require_known_label(
            source.sensitivity_class,
            known_sensitivity,
            "sensitivity class",
            paths["sources"],
        )
        _require_known_label(
            source.license_policy,
            known_licenses,
            "license policy label",
            paths["sources"],
        )

    for policy in bundle.access.acl_policies:
        if policy.visibility_label is not None:
            _require_known_label(
                policy.visibility_label,
                known_visibility,
                "visibility label",
                paths["access"],
            )
        _require_known_source_ids(policy.source_ids, set(source_ids), paths["access"])

    _require_known_source_ids(
        bundle.security.source_allowlist.source_ids,
        set(source_ids),
        paths["security"],
    )

    retention_ids = [
        retention.policy_id for retention in bundle.memory.retention_policies
    ]
    _raise_on_duplicates(retention_ids, "memory retention policies", paths["memory"])
    known_retention = set(retention_ids)
    for scope in bundle.memory.scopes:
        _require_known_label(
            scope.visibility_label,
            known_visibility,
            "visibility label",
            paths["memory"],
        )
        _require_known_label(
            scope.sensitivity_class,
            known_sensitivity,
            "sensitivity class",
            paths["memory"],
        )
        if scope.retention_policy not in known_retention:
            raise ConfigReferenceError(
                "unknown memory retention policy "
                f"{scope.retention_policy!r} referenced by scope {scope.scope!r}",
                path=paths["memory"],
            )


def _raise_on_duplicates(values: Iterable[str], label: str, path: Path) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise ConfigReferenceError(f"duplicate {label}: {joined}", path=path)


def _require_known_label(
    value: str,
    known_values: set[str],
    label: str,
    path: Path,
) -> None:
    if value not in known_values:
        raise ConfigReferenceError(
            f"unknown {label} {value!r}",
            path=path,
        )


def _require_known_source_ids(
    values: Iterable[str],
    known_source_ids: set[str],
    path: Path,
) -> None:
    for value in values:
        if value not in known_source_ids:
            raise ConfigReferenceError(
                f"unknown source ID {value!r}",
                path=path,
            )
