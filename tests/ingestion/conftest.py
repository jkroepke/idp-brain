from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, String, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from idp_brain.config.models import ExtractorProfileConfig
from idp_brain.ingestion.extractors import ArtifactExtractionContext
from idp_brain.models import Artifact, Base, IngestionRun, Source, SourceVersion

FORBIDDEN_RAW_VALUES = (
    "sk-test-ingestion-secret",
    "hunter2-ingestion",
    "ada@example.test",
    "raw diff --git a/private b/private",
)

INGESTION_OWNED_TABLES = (
    "sources",
    "source_versions",
    "source_changes",
    "change_versions",
    "artifacts",
    "artifact_versions",
    "artifact_extractions",
    "redaction_events",
    "license_findings",
    "chunks",
    "chunk_versions",
    "citations",
    "ingestion_runs",
)


@pytest.fixture()
def ingestion_session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory: sessionmaker[Session] = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    yield factory
    engine.dispose()


@pytest.fixture()
def migrated_postgres_engine(phase2_migrated_engine):
    return phase2_migrated_engine


@pytest.fixture()
def migrated_postgres_session_factory(
    migrated_postgres_engine: Engine,
) -> sessionmaker[Session]:
    return sessionmaker(bind=migrated_postgres_engine, expire_on_commit=False)


@pytest.fixture()
def extractor_profile() -> ExtractorProfileConfig:
    return ExtractorProfileConfig.model_validate(
        {
            "profile_id": "ingestion_docs",
            "family": "docs",
            "enabled": True,
            "file_patterns": ["**/*"],
            "include_generated": False,
            "include_vendored": False,
            "tools": [
                {
                    "tool_id": "builtin-ingestion",
                    "enabled": True,
                    "command": [],
                    "options": {
                        "chunk_size_chars": 500,
                        "chunk_overlap_chars": 50,
                    },
                }
            ],
            "validator_commands": [],
            "fallback_profile": None,
        }
    )


@pytest.fixture()
def artifact_context_factory() -> Callable[..., ArtifactExtractionContext]:
    def factory(
        path: str = "guide.md",
        role: str = "documentation",
        *,
        language: str | None = None,
        source_id: str = "source:ingestion",
        source_version_id: str = "source-version:ingestion",
        artifact_id: str | None = None,
        locator: str | None = None,
        sensitivity_class: str = "confidential",
        license_policy_label: str = "review_required",
        corpus_eligibility_label: str = "review_required",
    ) -> ArtifactExtractionContext:
        return ArtifactExtractionContext(
            artifact_id=artifact_id or f"artifact:{path}",
            source_id=source_id,
            source_version_id=source_version_id,
            path=path,
            logical_locator=locator or f"fixture:{path}",
            source_type="local_directory",
            artifact_role=role,
            language=language,
            extractor_profile="ingestion_docs",
            visibility_label="invited_users",
            sensitivity_class=sensitivity_class,
            license_policy_label=license_policy_label,
            corpus_eligibility_label=corpus_eligibility_label,
        )

    return factory


@pytest.fixture()
def add_ingestion_graph() -> Callable[[Session], None]:
    def add(session: Session) -> None:
        session.add(
            Source(
                id="source:ingestion",
                config_key="ingestion-source",
                name="Ingestion Source",
                source_type="local_directory",
                repository_url="https://example.test/repo.git",
                visibility_label="invited_users",
                sensitivity_class="confidential",
                license_policy_status="review_required",
                redaction_status="redacted",
            )
        )
        session.add(
            SourceVersion(
                id="source-version:ingestion",
                source_id="source:ingestion",
                version_label="snapshot",
                repository_url="https://example.test/repo.git",
                commit_sha="abc123",
                tag="v1.0.0",
                version="1.0.0",
                checksum="sha256:source-version",
                is_current=True,
                visibility_label="invited_users",
                sensitivity_class="confidential",
                license_policy_status="review_required",
                redaction_status="redacted",
            )
        )
        session.add(
            IngestionRun(
                id="ingestion:run",
                source_id="source:ingestion",
                source_version_id="source-version:ingestion",
                requested_ref="snapshot",
                status="completed",
                stats={},
                diagnostics={},
            )
        )
        session.add(
            Artifact(
                id="artifact:guide.md",
                artifact_key="guide.md",
                artifact_type="document",
                artifact_role="documentation",
                path="guide.md",
                source_id="source:ingestion",
                source_version_id="source-version:ingestion",
                source_type="local_directory",
                repository_url="https://example.test/repo.git",
                visibility_label="invited_users",
                sensitivity_class="confidential",
                license_policy_status="review_required",
                redaction_status="redacted",
                corpus_eligibility_label="review_required",
            )
        )
        session.flush()

    return add


def run_git(
    repository: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> str:
    current_env = os.environ.copy()
    current_env.update(
        {
            "GIT_AUTHOR_DATE": "2024-01-02T03:04:05+00:00",
            "GIT_COMMITTER_DATE": "2024-01-02T03:04:05+00:00",
        }
    )
    if env is not None:
        current_env.update(env)
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        env=current_env,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def assert_no_forbidden_ingestion_text(
    session: Session,
    *,
    forbidden_values: tuple[str, ...] = FORBIDDEN_RAW_VALUES,
) -> None:
    """Fail if forbidden raw values appear in any ingestion-owned text field."""

    violations: list[str] = []
    for table_name in INGESTION_OWNED_TABLES:
        table = Base.metadata.tables.get(table_name)
        if table is None:
            continue
        text_columns = [
            column
            for column in table.c
            if isinstance(column.type, String | Text | JSON)
        ]
        for column in text_columns:
            for value in session.scalars(select(column)).all():
                serialized = _serialized_text(value)
                if serialized is None:
                    continue
                for forbidden_value in forbidden_values:
                    if forbidden_value in serialized:
                        violations.append(f"{table_name}.{column.name}")
                        break

    assert not violations, "forbidden raw ingestion values persisted in: " + ", ".join(
        sorted(set(violations))
    )


def _serialized_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return repr(value)
