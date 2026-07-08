from __future__ import annotations

import pytest
from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from idp_brain.db import PHASE_2_TABLES
from idp_brain.models import (
    Artifact,
    ArtifactExtraction,
    ArtifactVersion,
    Base,
    ChangeVersion,
    Chunk,
    ChunkVersion,
    Citation,
    Claim,
    ClaimVersion,
    CorpusPolicyDefault,
    Embedding,
    EmbeddingJob,
    EmbeddingModel,
    Fact,
    FactVersion,
    IndexVersion,
    IngestionRun,
    LicenseFinding,
    RedactionEvent,
    Relationship,
    RelationshipVersion,
    RetrievalEvent,
    Source,
    SourceChange,
    SourceVersion,
)

pytestmark = pytest.mark.integration

FORBIDDEN_COLUMN_NAMES = {
    "raw_text",
    "raw_content",
    "unsanitized_text",
    "secret_value",
    "pii_value",
    "prompt_text",
    "provider_raw_response",
    "provider_response_raw",
    "raw_provider_response",
}
SAFETY_TABLES = {
    "artifacts",
    "artifact_extractions",
    "chunks",
    "citations",
    "facts",
    "claims",
    "relationships",
    "redaction_events",
    "license_findings",
    "retrieval_events",
    "embedding_jobs",
    "embeddings",
}


def _provenance() -> dict[str, object]:
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


def test_safety_tables_do_not_define_raw_or_sensitive_value_columns() -> None:
    for table_name in SAFETY_TABLES:
        column_names = set(Base.metadata.tables[table_name].columns.keys())
        assert column_names.isdisjoint(FORBIDDEN_COLUMN_NAMES)


def test_rebuilt_database_columns_preserve_safety_contracts(
    phase2_migrated_engine: Engine,
) -> None:
    inspector = inspect(phase2_migrated_engine)

    for table_name in SAFETY_TABLES:
        column_names = {
            column["name"]
            for column in inspector.get_columns(table_name, schema="public")
        }
        assert column_names.isdisjoint(FORBIDDEN_COLUMN_NAMES)


def test_minimal_sanitized_phase_2_graph_inserts(
    phase2_migrated_engine: Engine,
) -> None:
    with Session(phase2_migrated_engine) as session:
        session.add(
            CorpusPolicyDefault(
                id="corpus-policy:mvp",
                policy_version="phase-2",
                description="MVP fail-closed corpus defaults.",
            )
        )
        session.add(
            Source(
                id="source:test",
                config_key="test-source",
                name="Test Source",
                source_type="git",
                repository_url="https://example.test/repo.git",
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

        session.add(
            ChangeVersion(
                id="change-version:test",
                change_id="change:test",
                source_version_id="source-version:test:v1",
                version_label="v1.0.0",
            )
        )
        session.add(
            Artifact(
                id="artifact:test:readme",
                artifact_key="README.md@abc123",
                artifact_type="document",
                artifact_role="documentation",
                title="README",
                language="markdown",
                sanitized_content_hash="sha256:artifact",
                **_provenance(),
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
                diagnostics={"sanitized": True},
                sanitized_content_hash="sha256:artifact",
            )
        )
        session.flush()

        session.add(
            Chunk(
                id="chunk:test",
                chunk_key="README.md:1-5@abc123",
                artifact_id="artifact:test:readme",
                extraction_id="extraction:test",
                sanitized_text="Use declarative configuration for retrieval.",
                sanitized_content_hash="sha256:chunk",
                heading_path="Overview",
                symbol_path="tool.configuration",
                signature_text="configuration",
                artifact_path="README.md",
                language="markdown",
                artifact_role="documentation",
                chunk_kind="section",
                token_count=6,
                **_provenance(),
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
                **_provenance(),
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
                **_provenance(),
            )
        )
        session.flush()

        session.add(
            FactVersion(
                id="fact-version:test",
                fact_id="fact:test",
                source_version_id="source-version:test:v1",
                version_label="v1.0.0",
                is_current=True,
            )
        )
        session.add(
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
                **_provenance(),
            )
        )
        session.flush()

        session.add(
            ClaimVersion(
                id="claim-version:test",
                claim_id="claim:test",
                source_version_id="source-version:test:v1",
                version_label="v1.0.0",
                is_current=True,
            )
        )
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
                **_provenance(),
            )
        )
        session.flush()

        session.add(
            RelationshipVersion(
                id="relationship-version:test",
                relationship_id="relationship:test",
                source_version_id="source-version:test:v1",
                version_label="v1.0.0",
                is_current=True,
            )
        )
        session.add(
            RedactionEvent(
                id="redaction:event:test",
                ingestion_run_id="ingestion:test",
                source_id="source:test",
                source_version_id="source-version:test:v1",
                artifact_id="artifact:test:readme",
                chunk_id="chunk:test",
                citation_id="citation:test",
                detector_name="mock-redactor",
                detector_version="1.0.0",
                rule_id="synthetic-secret",
                marker="[REDACTED_SECRET]",
                match_count=1,
                location_locator="README.md:L1",
                sanitized_content_hash="sha256:chunk",
                redaction_profile="mvp-default",
                severity="high",
                redaction_status="redacted",
            )
        )
        session.add(
            LicenseFinding(
                id="license:finding:test",
                source_id="source:test",
                source_version_id="source-version:test:v1",
                artifact_id="artifact:test:readme",
                citation_id="citation:test",
                scanner_name="mock-license-scanner",
                scanner_version="1.0.0",
                license_expression="MIT",
                license_id="MIT",
                finding_location="README.md",
                confidence=0.99,
                policy_status="allowed",
            )
        )
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

        session.add(
            EmbeddingJob(
                id="embedding-job:test",
                chunk_id="chunk:test",
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test:inactive",
                sanitized_input_hash="sha256:chunk",
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
                vector=[0.0, 1.0, 0.0],
                dimensions=3,
                distance_metric="cosine",
            )
        )
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
                    "sensitivity_class": ["public"],
                    "redaction_status": ["redacted"],
                },
                selected_ids=["chunk:test"],
                primary_selected_chunk_id="chunk:test",
                primary_selected_citation_id="citation:test",
                primary_selected_artifact_id="artifact:test:readme",
                selected_chunk_ids=["chunk:test"],
                selected_citation_ids=["citation:test"],
                selected_artifact_ids=["artifact:test:readme"],
                ranking_diagnostics={"candidate_count": 1, "path": "exact"},
                redaction_status="redacted",
                corpus_eligibility_filter_result="allowed",
                active_index_version_id="index-version:test:inactive",
            )
        )
        session.commit()

        retrieval_event = session.scalar(select(RetrievalEvent))
        assert retrieval_event is not None
        assert retrieval_event.sanitized_query_preview == (
            "sanitized configuration lookup"
        )
        assert retrieval_event.selected_chunk_ids == ["chunk:test"]
        assert retrieval_event.trusted_filters["sensitivity_class"] == ["public"]

        embedding_job = session.get(EmbeddingJob, "embedding-job:test")
        assert embedding_job is not None
        assert embedding_job.status == "pending"
        assert embedding_job.provider_response_metadata == {
            "provider": "local",
            "mock": True,
        }

        chunk = session.get(Chunk, "chunk:test")
        assert chunk is not None
        assert chunk.source_allowlisted is True
        assert chunk.sensitivity_class == "public"
        assert chunk.license_policy_status == "allowed"
        assert chunk.redaction_status == "redacted"

        database_tables = set(inspect(phase2_migrated_engine).get_table_names())
        assert PHASE_2_TABLES <= database_tables
