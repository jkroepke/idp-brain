from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, create_engine, func, inspect, select
from sqlalchemy.orm import Session

from idp_brain.models import (
    RELATIONSHIP_TYPES,
    Artifact,
    ArtifactExtraction,
    ArtifactVersion,
    Base,
    ChangeVersion,
    Chunk,
    ChunkVersion,
    Citation,
    Claim,
    ClaimConflict,
    ClaimVersion,
    Fact,
    FactVersion,
    IngestionRun,
    Relationship,
    RelationshipVersion,
    Source,
    SourceChange,
    SourceVersion,
)

EXPECTED_TABLES = {
    "sources",
    "source_versions",
    "source_changes",
    "change_versions",
    "ingestion_runs",
    "artifacts",
    "artifact_versions",
    "artifact_extractions",
    "facts",
    "fact_versions",
    "claims",
    "claim_versions",
    "claim_conflicts",
    "relationships",
    "relationship_versions",
    "chunks",
    "chunk_versions",
    "citations",
    "corpus_policy_defaults",
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


def add_source_graph(session: Session) -> None:
    session.add(
        Source(
            id="source:test",
            config_key="test-source",
            name="Test Source",
            source_type="git",
            repository_url="https://example.test/repo.git",
            authority_rank=10,
        )
    )
    session.add(
        SourceVersion(
            id="source-version:test:v1",
            source_id="source:test",
            version_label="v1.0.0",
            repository_url="https://example.test/repo.git",
            commit_sha="abc123",
            tag="v1.0.0",
            version="1.0.0",
            checksum="sha256:example",
            is_current=True,
        )
    )
    session.flush()

    session.add(
        SourceChange(
            id="change:test",
            source_id="source:test",
            change_key="abc123",
            change_type="commit",
            commit_sha="abc123",
            title="Initial documented behavior",
        )
    )
    session.add(
        ChangeVersion(
            id="change-version:test",
            change_id="change:test",
            source_version_id="source-version:test:v1",
            version_label="v1.0.0",
        )
    )
    session.add(
        IngestionRun(
            id="ingestion:test",
            source_id="source:test",
            source_version_id="source-version:test:v1",
            requested_ref="v1.0.0",
            status="completed",
            stats={"artifacts": 1},
        )
    )
    session.flush()


def add_artifact_graph(session: Session) -> None:
    session.add(
        Artifact(
            id="artifact:test:readme",
            artifact_key="README.md@abc123",
            artifact_type="document",
            artifact_role="documentation",
            title="README",
            language="markdown",
            sanitized_content_hash="sha256:artifact",
            **provenance_kwargs(),
        )
    )
    session.flush()

    session.add(
        ArtifactVersion(
            id="artifact-version:test",
            artifact_id="artifact:test:readme",
            source_version_id="source-version:test:v1",
            version_label="v1.0.0",
            commit_sha="abc123",
            tag="v1.0.0",
            version="1.0.0",
            checksum="sha256:artifact",
            is_current=True,
        )
    )
    session.add(
        ArtifactExtraction(
            id="extraction:test",
            artifact_id="artifact:test:readme",
            ingestion_run_id="ingestion:test",
            source_id="source:test",
            source_version_id="source-version:test:v1",
            extractor_name="markdown",
            extractor_version="1.0.0",
            extractor_profile="docs_default",
            status="completed",
            diagnostics={},
            sanitized_content_hash="sha256:artifact",
        )
    )
    session.flush()


def add_evidence_graph(session: Session) -> None:
    session.add(
        Chunk(
            id="chunk:test",
            chunk_key="README.md:1-5@abc123",
            artifact_id="artifact:test:readme",
            extraction_id="extraction:test",
            sanitized_text="The tool supports declarative configuration.",
            sanitized_content_hash="sha256:chunk",
            heading_path="Overview",
            symbol_path="tool.configuration",
            signature_text="configuration",
            artifact_path="README.md",
            language="markdown",
            artifact_role="documentation",
            chunk_kind="section",
            token_count=6,
            **provenance_kwargs(),
        )
    )
    session.flush()

    session.add(
        ChunkVersion(
            id="chunk-version:test",
            chunk_id="chunk:test",
            source_version_id="source-version:test:v1",
            version_label="v1.0.0",
            commit_sha="abc123",
            tag="v1.0.0",
            version="1.0.0",
            checksum="sha256:chunk",
            is_current=True,
        )
    )
    session.add(
        Citation(
            id="citation:test",
            citation_key="README.md:1-5@abc123",
            source_url="https://example.test/repo/blob/abc123/README.md#L1-L5",
            artifact_id="artifact:test:readme",
            chunk_id="chunk:test",
            line_start=1,
            line_end=5,
            sanitized_content_hash="sha256:chunk",
            **provenance_kwargs(),
        )
    )
    session.flush()

    session.add(
        Fact(
            id="fact:test",
            fact_key="tool.configuration.support",
            artifact_id="artifact:test:readme",
            extraction_id="extraction:test",
            fact_type="capability",
            subject="tool",
            predicate="supports",
            normalized_value={"mode": "declarative configuration"},
            value_type="object",
            scope={"version": "v1.0.0"},
            confidence=0.95,
            authority_rank=10,
            primary_citation_id="citation:test",
            citation_ids=["citation:test"],
            sanitized_content_hash="sha256:chunk",
            **provenance_kwargs(),
        )
    )
    session.flush()

    session.add(
        FactVersion(
            id="fact-version:test",
            fact_id="fact:test",
            source_version_id="source-version:test:v1",
            version_label="v1.0.0",
            commit_sha="abc123",
            tag="v1.0.0",
            version="1.0.0",
            checksum="sha256:chunk",
            is_current=True,
        )
    )


def add_claim_graph(session: Session) -> None:
    session.add_all(
        [
            Claim(
                id="claim:test",
                claim_key="tool.supports.declarative",
                fact_id="fact:test",
                subject="tool",
                predicate="supports",
                normalized_value={"mode": "declarative configuration"},
                value_type="object",
                scope={"version": "v1.0.0"},
                confidence=0.95,
                authority_rank=10,
                primary_citation_id="citation:test",
                citation_ids=["citation:test"],
                sanitized_content_hash="sha256:chunk",
                **provenance_kwargs(),
            ),
            Claim(
                id="claim:competing",
                claim_key="tool.supports.imperative",
                fact_id="fact:test",
                subject="tool",
                predicate="supports",
                normalized_value={"mode": "imperative configuration"},
                value_type="object",
                scope={"version": "v1.0.0"},
                confidence=0.4,
                authority_rank=50,
                primary_citation_id="citation:test",
                citation_ids=["citation:test"],
                sanitized_content_hash="sha256:chunk",
                **provenance_kwargs(),
            ),
        ]
    )
    session.flush()

    session.add_all(
        [
            ClaimVersion(
                id="claim-version:test",
                claim_id="claim:test",
                source_version_id="source-version:test:v1",
                version_label="v1.0.0",
                commit_sha="abc123",
                tag="v1.0.0",
                version="1.0.0",
                checksum="sha256:chunk",
                is_current=True,
            ),
            ClaimVersion(
                id="claim-version:competing",
                claim_id="claim:competing",
                source_version_id="source-version:test:v1",
                version_label="v1.0.0",
                commit_sha="abc123",
                tag="v1.0.0",
                version="1.0.0",
                checksum="sha256:chunk",
                is_current=True,
            ),
            ClaimConflict(
                id="claim-conflict:test",
                conflict_key="tool.supports@v1.0.0",
                left_claim_id="claim:test",
                right_claim_id="claim:competing",
                primary_citation_id="citation:test",
                overlap_scope={"version": "v1.0.0"},
                evidence_citation_ids=["citation:test"],
            ),
        ]
    )


def add_relationship_graph(session: Session) -> None:
    session.add(
        Relationship(
            id="relationship:test",
            relationship_key="claim:test:cites:citation:test",
            relationship_type="cites",
            from_entity_type="claim",
            from_entity_id="claim:test",
            to_entity_type="citation",
            to_entity_id="citation:test",
            scope={"version": "v1.0.0"},
            confidence=0.95,
            authority_rank=10,
            primary_citation_id="citation:test",
            citation_ids=["citation:test"],
            sanitized_content_hash="sha256:chunk",
            **provenance_kwargs(),
        )
    )
    session.flush()

    session.add(
        RelationshipVersion(
            id="relationship-version:test",
            relationship_id="relationship:test",
            source_version_id="source-version:test:v1",
            version_label="v1.0.0",
            commit_sha="abc123",
            tag="v1.0.0",
            version="1.0.0",
            checksum="sha256:chunk",
            is_current=True,
        )
    )


def test_core_metadata_declares_only_phase_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES

    excluded_tables = {
        "embeddings",
        "embedding_jobs",
        "embedding_models",
        "access_policies",
        "redaction_events",
        "license_findings",
        "memory_items",
        "retrieval_events",
        "index_versions",
    }
    assert set(Base.metadata.tables).isdisjoint(excluded_tables)


def test_core_schema_creates_and_persists_minimal_graph() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)

        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == EXPECTED_TABLES

        with Session(engine) as session:
            add_source_graph(session)
            add_artifact_graph(session)
            add_evidence_graph(session)
            add_claim_graph(session)
            add_relationship_graph(session)
            session.commit()

            persisted_claim = session.get(Claim, "claim:test")
            assert persisted_claim is not None
            assert persisted_claim.citation_ids == ["citation:test"]
            assert session.scalar(select(func.count()).select_from(Relationship)) == 1
    finally:
        engine.dispose()


def test_chunks_expose_only_sanitized_content_columns() -> None:
    chunk_columns = set(Chunk.__table__.columns.keys())

    assert {
        "sanitized_text",
        "sanitized_content_hash",
        "heading_path",
        "symbol_path",
        "signature_text",
        "artifact_path",
        "source_type",
        "language",
        "artifact_role",
        "version_label",
    } <= chunk_columns

    forbidden_fragments = ("raw", "unsanitized", "original")
    assert not any(
        fragment in column_name
        for column_name in chunk_columns
        for fragment in forbidden_fragments
    )


def test_relationship_type_check_constraint_covers_initial_types() -> None:
    relationship_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in Relationship.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    relationship_type_check = relationship_checks[
        "ck_relationships_relationship_type_valid"
    ]
    for relationship_type in RELATIONSHIP_TYPES:
        assert f"'{relationship_type}'" in relationship_type_check


def test_claims_conflicts_and_relationships_require_primary_citation() -> None:
    for table in (Claim.__table__, ClaimConflict.__table__, Relationship.__table__):
        primary_citation = table.c.primary_citation_id

        assert primary_citation.nullable is False
        assert any(
            foreign_key.column.table.name == "citations"
            and foreign_key.column.name == "id"
            for foreign_key in primary_citation.foreign_keys
        )
