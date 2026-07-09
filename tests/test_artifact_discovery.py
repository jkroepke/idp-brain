from __future__ import annotations

from pathlib import Path

from idp_brain.config.models import SourceConfig
from idp_brain.ingestion.discovery import ArtifactDiscoveryService
from idp_brain.ingestion.source_snapshot import ArtifactCandidate, SourceSnapshot


def test_artifact_discovery_classifies_and_skips_defaults(tmp_path: Path) -> None:
    config_path = _write_sources_config(tmp_path)
    source = _source_config()
    snapshot = _snapshot(
        source,
        [
            "docs/guide.md",
            "src/app.py",
            "vendor/package/lib.py",
            "src/client.generated.ts",
            "docs/private.md",
            "openapi/service.yaml",
            "schema/user.schema.json",
        ],
    )

    discovered = ArtifactDiscoveryService(config_path=config_path).discover(snapshot)

    assert [artifact.path for artifact in discovered.artifacts] == [
        "docs/guide.md",
        "openapi/service.yaml",
        "schema/user.schema.json",
        "src/app.py",
    ]
    by_path = {artifact.path: artifact for artifact in discovered.artifacts}
    assert by_path["docs/guide.md"].artifact_role == "documentation"
    assert by_path["docs/guide.md"].extractor_profile == "docs_markdown_html"
    assert by_path["src/app.py"].artifact_role == "source_code"
    assert by_path["src/app.py"].language == "python"
    assert by_path["src/app.py"].extractor_profile == "source_code"
    assert by_path["openapi/service.yaml"].artifact_role == "openapi_spec"
    assert by_path["openapi/service.yaml"].extractor_profile == "openapi_specs"
    assert by_path["schema/user.schema.json"].artifact_role == "json_schema"

    skipped_by_path = {skipped.locator: skipped for skipped in discovered.skipped}
    assert skipped_by_path["vendor/package/lib.py"].reason == "vendored_file"
    assert skipped_by_path["vendor/package/lib.py"].vendored is True
    assert skipped_by_path["src/client.generated.ts"].reason == "generated_file"
    assert skipped_by_path["src/client.generated.ts"].generated is True
    assert skipped_by_path["docs/private.md"].reason == "excluded_by_glob"
    assert skipped_by_path["docs/private.md"].pattern == "docs/private.md"
    assert all(
        skipped.discovery_rule_version == "artifact-discovery-v1"
        for skipped in discovered.skipped
    )


def test_artifact_discovery_preserves_auditable_override(
    tmp_path: Path,
) -> None:
    config_path = _write_sources_config(tmp_path)
    source = _source_config(
        include_generated=True,
        include_vendored=True,
        discovery_override_reason="operator-approved-fixture",
    )
    snapshot = _snapshot(
        source,
        ["vendor/package/lib.py", "src/client.generated.ts"],
    )

    discovered = ArtifactDiscoveryService(config_path=config_path).discover(snapshot)

    assert [artifact.path for artifact in discovered.artifacts] == [
        "src/client.generated.ts",
        "vendor/package/lib.py",
    ]
    assert {artifact.override_reason for artifact in discovered.artifacts} == {
        "operator-approved-fixture"
    }
    assert {artifact.generated for artifact in discovered.artifacts} == {False, True}
    assert {artifact.vendored for artifact in discovered.artifacts} == {False, True}
    assert discovered.skipped == ()


def test_artifact_discovery_requires_explicit_exclude_override(
    tmp_path: Path,
) -> None:
    config_path = _write_sources_config(tmp_path)
    ordinary_source = _source_config(discovery_override_reason="operator-approved")
    overridden_source = _source_config(
        discovery_override_reason="operator-approved-exclude",
        override_exclude_paths=["docs/private.md"],
    )

    ordinary = ArtifactDiscoveryService(config_path=config_path).discover(
        _snapshot(ordinary_source, ["docs/private.md"])
    )
    overridden = ArtifactDiscoveryService(config_path=config_path).discover(
        _snapshot(overridden_source, ["docs/private.md"])
    )

    assert ordinary.artifacts == ()
    assert ordinary.skipped[0].reason == "excluded_by_glob"
    assert [artifact.path for artifact in overridden.artifacts] == ["docs/private.md"]
    assert overridden.artifacts[0].override_reason == "operator-approved-exclude"
    assert overridden.skipped == ()


def _source_config(**overrides: object) -> SourceConfig:
    payload = {
        "source_id": "discovery-fixture",
        "source_type": "local_directory",
        "local_path": "tests/fixtures/discovery",
        "tracked_refs": [],
        "version_strategy": "snapshot",
        "include_paths": ["**/*.md", "**/*.py", "**/*.ts", "**/*.yaml", "**/*.json"],
        "exclude_paths": ["docs/private.md"],
        "extractor_profile": "source_code",
        "source_priority": 25,
        "visibility_label": "invited_users",
        "corpus_eligibility": "review_required",
        "allowed_groups": ["developers"],
        "allowed_principals": [],
        "sensitivity_class": "internal",
        "license_policy": "review_required",
        "refresh_cadence": "manual",
        "enabled": True,
    }
    payload.update(overrides)
    return SourceConfig.model_validate(payload)


def _snapshot(
    source: SourceConfig,
    paths: list[str],
) -> SourceSnapshot:
    return SourceSnapshot(
        source=source,
        root_identifier="tests/fixtures/discovery",
        source_version_hash="0" * 64,
        version_label="snapshot:test",
        checksum="sha256:" + "0" * 64,
        artifacts=tuple(_artifact(path) for path in paths),
    )


def _artifact(path: str) -> ArtifactCandidate:
    return ArtifactCandidate(
        path=path,
        logical_locator=f"discovery-fixture:{path}",
        checksum="sha256:" + path.encode("utf-8").hex()[:16],
        size_bytes=10,
        mtime_ns=0,
        artifact_type="file",
        artifact_role=None,
        mime_type=None,
        language=None,
    )


def _write_sources_config(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "---\nconfig_version: 1\nkind: sources\nsources: []\n", encoding="utf-8"
    )
    return path
