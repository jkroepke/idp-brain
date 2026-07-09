from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, create_engine, inspect, select
from sqlalchemy.orm import Session

from idp_brain.models import (
    Artifact,
    Base,
    Chunk,
    Citation,
    Embedding,
    EmbeddingJob,
    EmbeddingModel,
    IndexVersion,
    IngestionRun,
    RetrievalEvent,
    Source,
    SourceVersion,
)

INDEX_EMBEDDING_TABLES = {
    "embedding_models",
    "index_versions",
    "embeddings",
    "embedding_jobs",
}
FORBIDDEN_COLUMN_FRAGMENTS = (
    "raw",
    "unsanitized",
    "input_text",
    "prompt",
    "api_key",
    "secret",
)


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
        "source_allowlisted": True,
        "sensitivity_class": "public",
        "license_policy_status": "allowed",
        "license_id": "MIT",
        "redaction_status": "redacted",
    }


def add_sanitized_chunk_graph(session: Session) -> None:
    session.add(
        Source(
            id="source:test",
            config_key="test-source",
            name="Test Source",
            source_type="git",
            source_allowlisted=True,
            sensitivity_class="public",
            license_policy_status="allowed",
            license_id="MIT",
            redaction_status="redacted",
        )
    )
    session.add(
        SourceVersion(
            id="source-version:test:v1",
            source_id="source:test",
            version_label="v1.0.0",
            commit_sha="abc123",
            is_current=True,
            source_allowlisted=True,
            sensitivity_class="public",
            license_policy_status="allowed",
            license_id="MIT",
            redaction_status="redacted",
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
            sanitized_text="Use declarative configuration for retrieval.",
            sanitized_content_hash="sha256:chunk",
            heading_path="Overview",
            artifact_path="README.md",
            language="markdown",
            chunk_kind="section",
            token_count=6,
            **provenance_kwargs(),
        )
    )
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


def add_mock_embedding_index(session: Session) -> None:
    session.add(
        EmbeddingModel(
            id="embedding-model:mock",
            provider_name="local",
            model_name="Deterministic Mock Embedding",
            provider_model_id="mock-embedding-v1",
            dimensions=3,
            modality="text",
            corpus_scope="docs",
            distance_metric="cosine",
            tokenizer_profile="mock-tokenizer",
            config_hash="sha256:embedding-model",
            deterministic=True,
            external_calls_allowed=False,
            promotion_status="mock",
        )
    )
    session.flush()

    session.add(
        IndexVersion(
            id="index-version:test:inactive",
            name="docs-hybrid-v1",
            index_kind="hybrid",
            corpus_scope="docs",
            source_scope={"source_ids": ["source:test"]},
            embedding_model_id="embedding-model:mock",
            bm25_profile="docs_default",
            vector_profile="docs_default",
            exact_index_profile="docs_default",
            relationship_profile="disabled",
            chunking_profile="default",
            reranker_profile="disabled",
            config_hash="sha256:index-version",
            status="inactive",
            built_from_ingestion_run_id="ingestion:test",
            failure_metadata={},
        )
    )
    session.flush()


def test_index_embedding_schema_creates_expected_tables_and_constraints() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        assert INDEX_EMBEDDING_TABLES <= set(inspector.get_table_names())

        embedding_model_checks = {
            constraint.name: str(constraint.sqltext)
            for constraint in EmbeddingModel.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }
        assert (
            "'mock'"
            in embedding_model_checks["ck_embedding_models_promotion_status_valid"]
        )
        assert (
            "'cosine'"
            in embedding_model_checks["ck_embedding_models_distance_metric_valid"]
        )
    finally:
        engine.dispose()


def test_mock_embedding_index_job_vector_and_retrieval_event_reference() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            add_sanitized_chunk_graph(session)
            add_mock_embedding_index(session)
            session.add(
                EmbeddingJob(
                    id="embedding-job:test",
                    chunk_id="chunk:test",
                    embedding_model_id="embedding-model:mock",
                    index_version_id="index-version:test:inactive",
                    sanitized_input_hash="sha256:chunk",
                    sanitized_content_hash="sha256:chunk",
                    status="pending",
                    attempt_count=0,
                    provider_request_hash="sha256:request",
                    provider_response_metadata={"provider": "local", "mock": True},
                )
            )
            session.add(
                Embedding(
                    id="embedding:test",
                    chunk_id="chunk:test",
                    embedding_model_id="embedding-model:mock",
                    index_version_id="index-version:test:inactive",
                    sanitized_input_hash="sha256:chunk",
                    sanitized_content_hash="sha256:chunk",
                    vector=[0.0, 1.0, 0.0],
                    dimensions=3,
                    distance_metric="cosine",
                )
            )
            session.add(
                RetrievalEvent(
                    id="retrieval:event:indexed",
                    ingestion_run_id="ingestion:test",
                    source_id="source:test",
                    source_version_id="source-version:test:v1",
                    query_hash="sha256:query",
                    sanitized_query_preview="sanitized configuration lookup",
                    query_token_count=3,
                    trusted_filters={"source_ids": ["source:test"]},
                    selected_ids=["chunk:test"],
                    primary_selected_chunk_id="chunk:test",
                    primary_selected_citation_id="citation:test",
                    primary_selected_artifact_id="artifact:test:readme",
                    selected_chunk_ids=["chunk:test"],
                    selected_citation_ids=["citation:test"],
                    selected_artifact_ids=["artifact:test:readme"],
                    ranking_diagnostics={"candidate_count": 1},
                    redaction_status="redacted",
                    corpus_eligibility_filter_result="allowed",
                    active_index_version_id="index-version:test:inactive",
                )
            )
            session.commit()

            model = session.get(EmbeddingModel, "embedding-model:mock")
            assert model is not None
            assert model.deterministic is True
            assert model.external_calls_allowed is False
            assert model.promotion_status == "mock"

            index_version = session.get(IndexVersion, "index-version:test:inactive")
            assert index_version is not None
            assert index_version.status == "inactive"
            assert index_version.embedding_model_id == "embedding-model:mock"

            job = session.get(EmbeddingJob, "embedding-job:test")
            assert job is not None
            assert job.sanitized_input_hash == "sha256:chunk"
            assert job.provider_response_metadata["mock"] is True

            embedding = session.scalar(select(Embedding))
            assert embedding is not None
            assert embedding.sanitized_input_hash == "sha256:chunk"
            assert embedding.sanitized_content_hash == "sha256:chunk"
            assert embedding.dimensions == 3
            assert embedding.is_active is True

            event = session.get(RetrievalEvent, "retrieval:event:indexed")
            assert event is not None
            assert event.active_index_version_id == "index-version:test:inactive"
    finally:
        engine.dispose()


def test_embedding_records_have_no_raw_text_or_provider_payload_columns() -> None:
    for table_name in INDEX_EMBEDDING_TABLES:
        column_names = set(Base.metadata.tables[table_name].columns.keys())
        assert not any(
            fragment in column_name
            for column_name in column_names
            for fragment in FORBIDDEN_COLUMN_FRAGMENTS
        )

    job_columns = set(EmbeddingJob.__table__.columns.keys())
    assert "sanitized_error_message" in job_columns
    assert "provider_response_metadata" in job_columns
    assert "provider_request_hash" in job_columns


def test_retrieval_event_active_index_version_is_nullable_foreign_key() -> None:
    column = RetrievalEvent.__table__.c.active_index_version_id

    assert column.nullable is True
    assert {foreign_key.column.table.name for foreign_key in column.foreign_keys} == {
        "index_versions"
    }
