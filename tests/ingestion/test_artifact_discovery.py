from __future__ import annotations

from pathlib import Path

from idp_brain.config.models import SourceConfig
from idp_brain.ingestion.discovery import ArtifactDiscoveryService
from idp_brain.ingestion.source_snapshot import ArtifactCandidate, SourceSnapshot


def test_discovery_excludes_generated_and_vendored_by_default(tmp_path: Path) -> None:
    source = _source_config()
    discovered = ArtifactDiscoveryService(config_path=_write_config(tmp_path)).discover(
        _snapshot(
            source,
            [
                "guide.md",
                "data.json",
                "generated.min.js",
                "vendor/vendor.txt",
                "private.md",
            ],
        )
    )

    assert [artifact.path for artifact in discovered.artifacts] == [
        "data.json",
        "guide.md",
    ]
    skipped = {item.locator: item for item in discovered.skipped}
    assert skipped["generated.min.js"].reason == "generated_file"
    assert skipped["vendor/vendor.txt"].reason == "vendored_file"
    assert skipped["private.md"].reason == "excluded_by_glob"
    assert all(
        item.discovery_rule_version == "artifact-discovery-v1"
        for item in skipped.values()
    )


def test_discovery_overrides_are_auditable(tmp_path: Path) -> None:
    source = _source_config(
        include_generated=True,
        include_vendored=True,
        override_exclude_paths=["private.md"],
        discovery_override_reason="operator-approved-ingestion-fixture",
    )
    discovered = ArtifactDiscoveryService(config_path=_write_config(tmp_path)).discover(
        _snapshot(source, ["generated.min.js", "vendor/vendor.txt", "private.md"])
    )

    assert [artifact.path for artifact in discovered.artifacts] == [
        "generated.min.js",
        "private.md",
        "vendor/vendor.txt",
    ]
    assert {artifact.override_reason for artifact in discovered.artifacts} == {
        "operator-approved-ingestion-fixture"
    }
    assert discovered.skipped == ()


def _source_config(**overrides: object) -> SourceConfig:
    payload = {
        "source_id": "ingestion-discovery",
        "source_type": "local_directory",
        "local_path": "tests/fixtures/ingestion/local",
        "tracked_refs": ["local-snapshot"],
        "version_strategy": "snapshot",
        "include_paths": ["**/*.md", "**/*.json", "**/*.js", "**/*.txt"],
        "exclude_paths": ["private.md"],
        "extractor_profile": "docs_markdown_html",
        "source_priority": 10,
        "visibility_label": "invited_users",
        "corpus_eligibility": "review_required",
        "allowed_groups": ["developers"],
        "allowed_principals": [],
        "sensitivity_class": "confidential",
        "license_policy": "review_required",
        "refresh_cadence": "manual",
        "enabled": True,
    }
    payload.update(overrides)
    return SourceConfig.model_validate(payload)


def _snapshot(source: SourceConfig, paths: list[str]) -> SourceSnapshot:
    return SourceSnapshot(
        source=source,
        root_identifier="tests/fixtures/ingestion/local",
        source_version_hash="0" * 64,
        version_label="snapshot",
        checksum="sha256:snapshot",
        artifacts=tuple(
            ArtifactCandidate(
                path=path,
                logical_locator=f"ingestion-discovery:{path}",
                checksum=f"sha256:{path}",
                size_bytes=10,
                mtime_ns=0,
                artifact_type="file",
                artifact_role=None,
                mime_type=None,
                language=None,
            )
            for path in paths
        ),
    )


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "extractors.yaml"
    path.write_text(
        Path("config/extractors.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return path
