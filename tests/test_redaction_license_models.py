from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, create_engine, inspect, select
from sqlalchemy.orm import Session

from idp_brain.models import (
    Artifact,
    Base,
    Chunk,
    Citation,
    IngestionRun,
    LicenseFinding,
    RedactionEvent,
    RetrievalEvent,
    Source,
    SourceVersion,
)

EVENT_TABLES = {
    "redaction_events",
    "license_findings",
    "retrieval_events",
}
FORBIDDEN_COLUMN_NAMES = {
    "raw_value",
    "secret_value",
    "pii_value",
    "raw_text",
    "unsanitized_text",
    "prompt_text",
}


def provenance_kwargs() -> dict[str, Any]:
    return {
        "source_id": "source:test",
        "source_version_id": "source-version:test:v1",
        "repository_url": "https://example.test/repo.git",
        "artifact_url": "https://example.test/repo/blob/v1/README.md",
        "commit_sha": "abc123",
        "tag": "v1.0.0",
        "version": "1.0.0",
        "version_label": "v1.0.0",
        "checksum": "sha256:example",
        "path": "README.md",
        "logical_locator": "docs/getting-started",
        "source_type": "markdown",
        "extractor_name": "markdown",
        "extractor_version": "1.0.0",
        "extractor_profile": "docs_default",
    }


def add_minimal_auditable_graph(session: Session) -> None:
    session.add(
        Source(
            id="source:test",
            config_key="test-source",
            name="Test Source",
            source_type="git",
        )
    )
    session.add(
        SourceVersion(
            id="source-version:test:v1",
            source_id="source:test",
            version_label="v1.0.0",
            commit_sha="abc123",
            is_current=True,
        )
    )
    session.add(
        IngestionRun(
            id="ingestion:test",
            source_id="source:test",
            source_version_id="source-version:test:v1",
            requested_ref="v1.0.0",
            status="completed",
            stats={},
        )
    )
    session.flush()

    session.add(
        Artifact(
            id="artifact:test:readme",
            artifact_key="README.md@abc123",
            artifact_type="document",
            title="README",
            language="markdown",
            sanitized_content_hash="sha256:artifact",
            **provenance_kwargs(),
        )
    )
    session.flush()

    session.add(
        Chunk(
            id="chunk:test",
            chunk_key="README.md:1-2@abc123",
            artifact_id="artifact:test:readme",
            sanitized_text="Use the sanitized token [REDACTED_SECRET].",
            sanitized_content_hash="sha256:chunk",
            heading_path="Overview",
            artifact_path="README.md",
            language="markdown",
            chunk_kind="section",
            token_count=6,
            **provenance_kwargs(),
        )
    )
    session.flush()

    session.add(
        Citation(
            id="citation:test",
            citation_key="README.md:1-2@abc123",
            source_url="https://example.test/repo/blob/abc123/README.md#L1-L2",
            artifact_id="artifact:test:readme",
            chunk_id="chunk:test",
            line_start=1,
            line_end=2,
            sanitized_content_hash="sha256:chunk",
            **provenance_kwargs(),
        )
    )
    session.flush()


def test_redaction_event_persists_only_marker_and_count_metadata() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            add_minimal_auditable_graph(session)
            session.add(
                RedactionEvent(
                    id="redaction:event:test",
                    ingestion_run_id="ingestion:test",
                    source_id="source:test",
                    source_version_id="source-version:test:v1",
                    artifact_id="artifact:test:readme",
                    chunk_id="chunk:test",
                    citation_id="citation:test",
                    detector_name="gitleaks",
                    detector_version="8.x",
                    rule_id="generic-api-key",
                    marker="[REDACTED_SECRET]",
                    match_count=1,
                    location_locator="README.md:L1",
                    sanitized_content_hash="sha256:chunk",
                    redaction_profile="mvp-default",
                    severity="high",
                    redaction_status="redacted",
                )
            )
            session.commit()

            event = session.get(RedactionEvent, "redaction:event:test")
            assert event is not None
            assert event.marker == "[REDACTED_SECRET]"
            assert event.match_count == 1
            assert event.sanitized_content_hash == "sha256:chunk"
    finally:
        engine.dispose()


def test_license_finding_records_scanner_provenance_and_policy_status() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            add_minimal_auditable_graph(session)
            session.add(
                LicenseFinding(
                    id="license:finding:test",
                    source_id="source:test",
                    source_version_id="source-version:test:v1",
                    artifact_id="artifact:test:readme",
                    citation_id="citation:test",
                    scanner_name="scancode-toolkit",
                    scanner_version="32.x",
                    license_expression="MIT",
                    license_id="MIT",
                    copyright_notice="Copyright Example",
                    finding_location="README.md",
                    confidence=0.99,
                    policy_status="allowed",
                )
            )
            session.commit()

            finding = session.get(LicenseFinding, "license:finding:test")
            assert finding is not None
            assert finding.scanner_name == "scancode-toolkit"
            assert finding.license_id == "MIT"
            assert finding.policy_status == "allowed"
    finally:
        engine.dispose()


def test_sanitized_retrieval_event_does_not_require_index_versions() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            add_minimal_auditable_graph(session)
            session.add(
                RetrievalEvent(
                    id="retrieval:event:test",
                    ingestion_run_id="ingestion:test",
                    source_id="source:test",
                    source_version_id="source-version:test:v1",
                    query_hash="sha256:query",
                    sanitized_query_preview="sanitized configuration lookup",
                    query_token_count=3,
                    trusted_filters={
                        "source_ids": ["source:test"],
                        "license_policy_status": ["allowed"],
                    },
                    selected_ids=["chunk:test"],
                    primary_selected_chunk_id="chunk:test",
                    primary_selected_citation_id="citation:test",
                    primary_selected_artifact_id="artifact:test:readme",
                    selected_chunk_ids=["chunk:test"],
                    selected_citation_ids=["citation:test"],
                    selected_artifact_ids=["artifact:test:readme"],
                    ranking_diagnostics={"fusion": "rrf", "candidate_count": 1},
                    redaction_status="redacted",
                    corpus_eligibility_filter_result="allowed",
                    active_index_version_id=None,
                )
            )
            session.commit()

            event = session.scalar(select(RetrievalEvent))
            assert event is not None
            assert event.active_index_version_id is None
            assert event.primary_selected_chunk_id == "chunk:test"
            assert event.primary_selected_citation_id == "citation:test"
            assert event.primary_selected_artifact_id == "artifact:test:readme"
            assert event.selected_citation_ids == ["citation:test"]
            assert event.ranking_diagnostics["candidate_count"] == 1

            active_index_column = RetrievalEvent.__table__.c.active_index_version_id
            assert active_index_column.nullable is True
            assert {
                foreign_key.column.table.name
                for foreign_key in active_index_column.foreign_keys
            } == {"index_versions"}
    finally:
        engine.dispose()


def test_policy_event_tables_avoid_unsafe_raw_value_columns() -> None:
    for table_name in EVENT_TABLES:
        table = Base.metadata.tables[table_name]
        assert set(table.columns.keys()).isdisjoint(FORBIDDEN_COLUMN_NAMES)

    for model in (RedactionEvent, RetrievalEvent):
        column_names = set(model.__table__.columns.keys())
        assert not any(
            forbidden_name in column_name
            for column_name in column_names
            for forbidden_name in FORBIDDEN_COLUMN_NAMES
        )


def test_policy_event_schema_links_to_auditable_source_records() -> None:
    expected_foreign_tables = {
        "redaction_events": {
            "ingestion_runs",
            "sources",
            "source_versions",
            "artifacts",
            "chunks",
            "citations",
        },
        "license_findings": {
            "sources",
            "source_versions",
            "artifacts",
            "citations",
        },
        "retrieval_events": {
            "ingestion_runs",
            "sources",
            "source_versions",
            "chunks",
            "citations",
            "artifacts",
            "index_versions",
        },
    }

    for table_name, expected_tables in expected_foreign_tables.items():
        foreign_tables = {
            foreign_key.column.table.name
            for foreign_key in Base.metadata.tables[table_name].foreign_keys
        }
        assert expected_tables <= foreign_tables


def test_sanitized_event_tables_create_with_expected_constraints() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        assert EVENT_TABLES <= set(inspector.get_table_names())

        for table_name in EVENT_TABLES:
            constraint_text = " ".join(
                str(constraint.sqltext)
                for constraint in Base.metadata.tables[table_name].constraints
                if isinstance(constraint, CheckConstraint)
            )
            assert "raw_value" not in constraint_text
            assert "secret_value" not in constraint_text

        assert "redaction_status" in {
            column.name for column in RedactionEvent.__table__.columns
        }
        assert "policy_status" in {
            column.name for column in LicenseFinding.__table__.columns
        }
        assert "corpus_eligibility_filter_result" in {
            column.name for column in RetrievalEvent.__table__.columns
        }
    finally:
        engine.dispose()
