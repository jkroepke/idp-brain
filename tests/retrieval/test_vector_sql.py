from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.embeddings import EmbeddingProviderRegistry
from idp_brain.models import Base
from idp_brain.retrieval import (
    RetrievalFilters,
    VectorCandidateRetriever,
    VectorRetrievalProfile,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False, future=True)
    with factory() as current_session:
        yield current_session
    engine.dispose()


def test_vector_postgres_sql_joins_filtered_chunks_before_distance_ordering(
    session: Session,
) -> None:
    statement = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([]),
    )._postgres_vector_select(
        [0.0, 1.0, 0.0],
        RetrievalFilters(source_ids=("src:docs",)),
        _profile(),
        5,
        retrieval_strategy="exact",
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    filtered_scope_index = compiled.index("WITH filtered_chunks AS MATERIALIZED")
    filter_predicate_index = compiled.index("chunks.source_allowlisted IS true")
    candidate_scope_index = compiled.index(
        "FROM embeddings JOIN filtered_chunks "
        "ON filtered_chunks.chunk_id = embeddings.chunk_id"
    )
    model_filter_index = compiled.index("embeddings.embedding_model_id =")
    distance_order_index = compiled.index("ORDER BY distance ASC")

    assert filtered_scope_index < filter_predicate_index
    assert filter_predicate_index < candidate_scope_index
    assert candidate_scope_index < model_filter_index
    assert model_filter_index < distance_order_index
    assert "embeddings.vector <=>" in compiled
    assert "CAST(embeddings.vector AS VECTOR" not in compiled
    assert "embeddings.dimensions =" in compiled


def test_vector_postgres_sql_requires_model_index_and_active_filters(
    session: Session,
) -> None:
    statement = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([]),
    )._postgres_vector_select(
        [0.0, 1.0, 0.0],
        RetrievalFilters(),
        _profile(),
        5,
        retrieval_strategy="exact",
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "embeddings.embedding_model_id =" in compiled
    assert "embeddings.index_version_id =" in compiled
    assert "embeddings.is_active IS true" in compiled
    assert "embeddings.dimensions =" in compiled
    assert "license_policy_status IN" in compiled
    assert "redaction_status IN" in compiled
    assert "fused_score" not in compiled


def test_vector_postgres_broad_sql_uses_hnsw_index_expression(
    session: Session,
) -> None:
    statement = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([]),
    )._postgres_vector_select(
        [0.0] * 32,
        RetrievalFilters(),
        _profile(),
        5,
        retrieval_strategy="hnsw",
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "CAST(embeddings.vector AS VECTOR(32)) <=>" in compiled
    assert "embeddings.dimensions = 32" in compiled
    assert "embeddings.dimensions = %(dimensions_" not in compiled
    assert "embeddings.is_active IS true" in compiled
    assert compiled.index("CAST(embeddings.vector AS VECTOR(32)) <=>") < compiled.index(
        "ORDER BY distance ASC"
    )


def test_vector_postgres_broad_sql_falls_back_to_base_vector_for_unindexed_dimension(
    session: Session,
) -> None:
    statement = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([]),
    )._postgres_vector_select(
        [0.0, 1.0, 0.0],
        RetrievalFilters(),
        _profile(),
        5,
        retrieval_strategy="hnsw",
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "embeddings.vector <=>" in compiled
    assert "CAST(embeddings.vector AS VECTOR" not in compiled
    assert "embeddings.dimensions =" in compiled


def test_vector_fallback_sql_mirrors_filtered_chunk_scope(session: Session) -> None:
    statement = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([]),
    )._fallback_scope_select(
        RetrievalFilters(source_ids=("src:docs",)),
        _profile(),
        dimensions=3,
    )

    compiled = str(
        statement.compile(
            dialect=sqlite.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "WITH filtered_chunks AS" in compiled
    assert (
        "FROM embeddings JOIN filtered_chunks "
        "ON filtered_chunks.chunk_id = embeddings.chunk_id"
    ) in compiled
    assert compiled.index("chunks.source_allowlisted IS 1") < compiled.index(
        "FROM embeddings JOIN filtered_chunks"
    )


def _profile() -> VectorRetrievalProfile:
    return VectorRetrievalProfile(
        profile_id="docs_vector",
        embedding_profile_id="docs_default",
        embedding_model_id="embedding-model:mock",
        index_version_id="index-version:test",
        candidate_limit=50,
        hnsw_ef_search=64,
        exact_search_threshold=10,
    )
