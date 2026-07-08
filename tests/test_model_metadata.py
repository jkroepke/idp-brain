from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint

from idp_brain.db import PHASE_2_TABLES
from idp_brain.models import Base

CANONICAL_PHASE_2_TABLES = PHASE_2_TABLES - {"alembic_version"}
FILTER_INDEX_TABLES = {
    "sources": "ix_sources_filter_pushdown",
    "source_versions": "ix_source_versions_filter_pushdown",
    "artifacts": "ix_artifacts_filter_pushdown",
    "chunks": "ix_chunks_filter_pushdown",
    "citations": "ix_citations_filter_pushdown",
    "facts": "ix_facts_filter_pushdown",
    "claims": "ix_claims_filter_pushdown",
    "relationships": "ix_relationships_filter_pushdown",
}
VERSION_MEMBERSHIP_TABLES = {
    "artifact_versions": ("artifact_id", "source_version_id"),
    "chunk_versions": ("chunk_id", "source_version_id"),
    "fact_versions": ("fact_id", "source_version_id"),
    "claim_versions": ("claim_id", "source_version_id"),
    "relationship_versions": ("relationship_id", "source_version_id"),
}


def _foreign_tables(table_name: str, column_name: str) -> set[str]:
    column = Base.metadata.tables[table_name].c[column_name]
    return {foreign_key.column.table.name for foreign_key in column.foreign_keys}


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _check_constraint_sql(table_name: str) -> str:
    checks = [
        str(constraint.sqltext)
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, CheckConstraint)
    ]
    return "\n".join(checks)


def test_model_metadata_declares_canonical_phase_2_tables() -> None:
    assert set(Base.metadata.tables) == CANONICAL_PHASE_2_TABLES


def test_required_foreign_keys_link_phase_2_graph() -> None:
    expected_foreign_keys = {
        ("source_versions", "source_id"): {"sources"},
        ("source_changes", "source_id"): {"sources"},
        ("change_versions", "change_id"): {"source_changes"},
        ("change_versions", "source_version_id"): {"source_versions"},
        ("ingestion_runs", "source_id"): {"sources"},
        ("ingestion_runs", "source_version_id"): {"source_versions"},
        ("artifacts", "source_id"): {"sources"},
        ("artifacts", "source_version_id"): {"source_versions"},
        ("artifact_versions", "artifact_id"): {"artifacts"},
        ("artifact_versions", "source_version_id"): {"source_versions"},
        ("artifact_extractions", "artifact_id"): {"artifacts"},
        ("facts", "artifact_id"): {"artifacts"},
        ("facts", "primary_citation_id"): {"citations"},
        ("chunks", "artifact_id"): {"artifacts"},
        ("chunks", "extraction_id"): {"artifact_extractions"},
        ("citations", "artifact_id"): {"artifacts"},
        ("citations", "chunk_id"): {"chunks"},
        ("claims", "fact_id"): {"facts"},
        ("claims", "primary_citation_id"): {"citations"},
        ("claim_conflicts", "left_claim_id"): {"claims"},
        ("claim_conflicts", "right_claim_id"): {"claims"},
        ("relationships", "primary_citation_id"): {"citations"},
        ("redaction_events", "chunk_id"): {"chunks"},
        ("license_findings", "artifact_id"): {"artifacts"},
        ("retrieval_events", "active_index_version_id"): {"index_versions"},
        ("index_versions", "embedding_model_id"): {"embedding_models"},
        ("index_versions", "built_from_ingestion_run_id"): {"ingestion_runs"},
        ("embedding_jobs", "chunk_id"): {"chunks"},
        ("embedding_jobs", "embedding_model_id"): {"embedding_models"},
        ("embedding_jobs", "index_version_id"): {"index_versions"},
        ("embeddings", "chunk_id"): {"chunks"},
        ("embeddings", "embedding_model_id"): {"embedding_models"},
        ("embeddings", "index_version_id"): {"index_versions"},
    }

    for (table_name, column_name), foreign_tables in expected_foreign_keys.items():
        assert foreign_tables <= _foreign_tables(table_name, column_name)


def test_required_uniqueness_and_nullable_lineage_contracts() -> None:
    assert ("config_key",) in _unique_column_sets("sources")
    assert ("source_id", "version_label") in _unique_column_sets("source_versions")
    assert ("source_id", "artifact_key") in _unique_column_sets("artifacts")
    assert ("source_id", "chunk_key") in _unique_column_sets("chunks")
    assert ("citation_key",) in _unique_column_sets("citations")
    assert ("source_id", "fact_key") in _unique_column_sets("facts")
    assert ("source_id", "claim_key") in _unique_column_sets("claims")
    assert ("source_id", "relationship_key") in _unique_column_sets("relationships")
    assert ("provider_name", "provider_model_id", "config_hash") in (
        _unique_column_sets("embedding_models")
    )
    assert (
        "chunk_id",
        "embedding_model_id",
        "index_version_id",
        "sanitized_input_hash",
    ) in _unique_column_sets("embeddings")

    for table_name, unique_columns in VERSION_MEMBERSHIP_TABLES.items():
        assert unique_columns in _unique_column_sets(table_name)
        assert Base.metadata.tables[table_name].c.first_containing_version_id.nullable
        assert Base.metadata.tables[table_name].c.last_containing_version_id.nullable


def test_filter_indexes_cover_future_retrieval_pushdown() -> None:
    for table_name, index_name in FILTER_INDEX_TABLES.items():
        table = Base.metadata.tables[table_name]
        index_names = {index.name for index in table.indexes}
        assert index_name in index_names

        index = next(index for index in table.indexes if index.name == index_name)
        indexed_columns = {column.name for column in index.columns}
        assert {
            "source_allowlisted",
            "sensitivity_class",
            "license_policy_status",
            "redaction_status",
        } <= indexed_columns

    assert "ix_citations_chunk_id" in {
        index.name for index in Base.metadata.tables["citations"].indexes
    }
    assert "ix_retrieval_events_query_hash" in {
        index.name for index in Base.metadata.tables["retrieval_events"].indexes
    }
    assert "ix_embedding_jobs_status_retry" in {
        index.name for index in Base.metadata.tables["embedding_jobs"].indexes
    }


def test_corpus_eligibility_checks_fail_closed_on_metadata_tables() -> None:
    for table_name in FILTER_INDEX_TABLES:
        checks = _check_constraint_sql(table_name)
        assert "source_allowlisted" not in checks or "false" not in checks
        assert "license_policy_status" in checks
        assert "sensitivity_class" in checks
        assert "redaction_status" in checks
        assert "license_id" in checks

    defaults = Base.metadata.tables["corpus_policy_defaults"]
    assert defaults.c.source_allowlist_default.default is not None
    assert "source_allowlist_default = false" in _check_constraint_sql(
        "corpus_policy_defaults"
    )
