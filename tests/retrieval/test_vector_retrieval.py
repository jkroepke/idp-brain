from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.config.models import EmbeddingProfileConfig
from idp_brain.db import assert_vector_available
from idp_brain.embeddings import (
    DeterministicMockEmbeddingProvider,
    EmbeddingProviderConfigError,
    EmbeddingProviderRegistry,
    EmbeddingVector,
)
from idp_brain.models import (
    Artifact,
    Base,
    Chunk,
    ChunkVersion,
    Embedding,
    EmbeddingModel,
    IndexVersion,
    Source,
    SourceVersion,
)
from idp_brain.retrieval import (
    RetrievalFilters,
    RetrievalQuery,
    VectorCandidateRetriever,
    VectorRetrievalProfile,
)
from idp_brain.retrieval.vector import _query_embedding_input


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False, future=True)
    with factory() as current_session:
        yield current_session
    engine.dispose()


def test_vector_retriever_returns_ranked_metadata_only(session: Session) -> None:
    query = RetrievalQuery(query_text="vector retrieval")
    filters = RetrievalFilters(source_ids=("source:test",))
    profile = _vector_profile()
    provider = DeterministicMockEmbeddingProvider(_embedding_profile())
    query_vector = provider.embed([_query_embedding_input(query, filters, profile)])[0]
    _add_graph(session, query_vector=query_vector.values)
    session.commit()

    candidates = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([_embedding_profile()]),
        deterministic_fallback=True,
    ).retrieve(query, filters, profile, limit=5)

    assert [candidate.chunk_id for candidate in candidates] == [
        "chunk:expected",
        "chunk:other",
    ]
    expected = candidates[0]
    assert expected.retrieval_path == "vector"
    assert expected.rank == 1
    assert expected.matched_fields == ()
    assert expected.diagnostics["cosine_distance"] == pytest.approx(0.0)
    assert expected.diagnostics["embedding_model_id"] == "embedding-model:mock"
    assert expected.diagnostics["index_version_id"] == "index-version:test"
    assert "bm25_score" not in expected.diagnostics
    assert "fused_score" not in expected.diagnostics
    assert "sanitized_text" not in expected.metadata
    assert "raw_text" not in expected.model_dump_json()


def test_vector_filters_apply_before_candidates_are_exposed(session: Session) -> None:
    query = RetrievalQuery(query_text="vector retrieval")
    filters = RetrievalFilters()
    profile = _vector_profile()
    provider = DeterministicMockEmbeddingProvider(_embedding_profile())
    query_vector = provider.embed([_query_embedding_input(query, filters, profile)])[0]
    _add_graph(session, query_vector=query_vector.values)
    _add_chunk(
        session,
        "chunk:denied-license",
        "safe vector retrieval",
        license_policy_status="denied",
        vector=query_vector.values,
    )
    _add_chunk(
        session,
        "chunk:restricted",
        "safe vector retrieval",
        sensitivity_class="restricted",
        vector=query_vector.values,
    )
    _add_chunk(
        session,
        "chunk:not-current",
        "safe vector retrieval",
        vector=query_vector.values,
        is_current=False,
    )
    session.commit()

    candidates = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([_embedding_profile()]),
        deterministic_fallback=True,
    ).retrieve(query, filters, profile, limit=10)

    assert [candidate.chunk_id for candidate in candidates] == [
        "chunk:expected",
        "chunk:other",
    ]


def test_vector_retrieval_requires_active_model_and_index_filters(
    session: Session,
) -> None:
    query = RetrievalQuery(query_text="vector retrieval")
    filters = RetrievalFilters()
    profile = _vector_profile()
    provider = DeterministicMockEmbeddingProvider(_embedding_profile())
    query_vector = provider.embed([_query_embedding_input(query, filters, profile)])[0]
    _add_graph(session, query_vector=query_vector.values)
    session.add(
        EmbeddingModel(
            id="embedding-model:other",
            provider_name="mock",
            model_name="deterministic-docs-other-v1",
            provider_model_id="deterministic-docs-other-v1",
            dimensions=3,
            modality="text",
            corpus_scope="docs",
            distance_metric="cosine",
            config_hash="sha256:model-other",
            deterministic=True,
            promotion_status="mock",
        )
    )
    session.add(
        Embedding(
            id="embedding:wrong-model",
            chunk_id="chunk:other",
            embedding_model_id="embedding-model:other",
            index_version_id="index-version:test",
            sanitized_input_hash="sha256:wrong-model",
            sanitized_content_hash="sha256:wrong-model",
            vector=query_vector.values,
            dimensions=3,
            distance_metric="cosine",
            is_active=True,
        )
    )
    session.add(
        Embedding(
            id="embedding:inactive",
            chunk_id="chunk:other",
            embedding_model_id="embedding-model:mock",
            index_version_id="index-version:test",
            sanitized_input_hash="sha256:inactive",
            sanitized_content_hash="sha256:inactive",
            vector=query_vector.values,
            dimensions=3,
            distance_metric="cosine",
            is_active=False,
        )
    )
    session.commit()

    candidates = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([_embedding_profile()]),
        deterministic_fallback=True,
    ).retrieve(query, filters, profile, limit=10)

    assert candidates[0].chunk_id == "chunk:expected"
    assert candidates[0].diagnostics["cosine_distance"] == pytest.approx(0.0, abs=1e-7)
    assert candidates[1].chunk_id == "chunk:other"
    assert candidates[1].diagnostics["cosine_distance"] > 0


def test_vector_retrieval_requires_active_model_and_index_profiles(
    session: Session,
) -> None:
    query = RetrievalQuery(query_text="vector retrieval")
    filters = RetrievalFilters()
    profile = _vector_profile()
    provider = DeterministicMockEmbeddingProvider(_embedding_profile())
    query_vector = provider.embed([_query_embedding_input(query, filters, profile)])[0]
    _add_graph(session, query_vector=query_vector.values)
    model = session.get(EmbeddingModel, "embedding-model:mock")
    index_version = session.get(IndexVersion, "index-version:test")
    assert model is not None
    assert index_version is not None

    model.promotion_status = "retired"
    session.commit()
    retriever = VectorCandidateRetriever(
        session,
        provider_registry=EmbeddingProviderRegistry([_embedding_profile()]),
        deterministic_fallback=True,
    )

    assert retriever.retrieve(query, filters, profile, limit=10) == []

    model.promotion_status = "mock"
    index_version.status = "retired"
    session.commit()

    assert retriever.retrieve(query, filters, profile, limit=10) == []


def test_inactive_or_missing_profiles_return_before_provider_embed(
    session: Session,
) -> None:
    query = RetrievalQuery(query_text="vector retrieval")
    filters = RetrievalFilters()
    profile = _vector_profile()
    _add_graph(session, query_vector=[1.0, 0.0, 0.0])
    model = session.get(EmbeddingModel, "embedding-model:mock")
    assert model is not None
    model.promotion_status = "inactive"
    session.commit()
    registry = _SpyRegistry()
    retriever = VectorCandidateRetriever(
        session,
        provider_registry=registry,  # type: ignore[arg-type]
        deterministic_fallback=True,
    )

    assert retriever.retrieve(query, filters, profile, limit=10) == []
    assert registry.resolve_calls == 0
    assert registry.provider.embed_calls == 0

    model.promotion_status = "mock"
    session.commit()
    missing_index_profile = VectorRetrievalProfile(
        profile_id="docs_vector",
        embedding_profile_id="docs_default",
        embedding_model_id="embedding-model:mock",
        index_version_id="index-version:missing",
        candidate_limit=10,
        hnsw_ef_search=64,
        exact_search_threshold=10,
    )

    assert retriever.retrieve(query, filters, missing_index_profile, limit=10) == []
    assert registry.resolve_calls == 0
    assert registry.provider.embed_calls == 0


def test_external_embedding_provider_fails_closed(session: Session) -> None:
    external = EmbeddingProfileConfig.model_construct(
        profile_id="external-docs",
        provider_id="openai",
        model_name="text-embedding-3-small",
        enabled=True,
        external=True,
        deterministic=False,
        dimensions=1536,
        batch_size=16,
        timeout_seconds=30,
        required_env_vars=[],
        token_limit=8191,
        options={},
    )
    profile = _vector_profile(embedding_profile_id="external-docs")
    _add_graph(session, query_vector=[1.0, 0.0, 0.0])
    session.commit()

    with pytest.raises(EmbeddingProviderConfigError, match="requires"):
        VectorCandidateRetriever(
            session,
            provider_registry=EmbeddingProviderRegistry([external]),
            deterministic_fallback=True,
        ).retrieve(RetrievalQuery(query_text="safe query"), RetrievalFilters(), profile)


@pytest.mark.integration
@pytest.mark.requires_pgvector
def test_vector_retriever_uses_pgvector_distance_ordering(
    phase2_migrated_engine: Engine,
) -> None:
    assert_vector_available(phase2_migrated_engine)
    query = RetrievalQuery(query_text="vector retrieval")
    filters = RetrievalFilters(source_ids=("source:test",))
    profile = _vector_profile()
    provider = DeterministicMockEmbeddingProvider(_embedding_profile())
    query_vector = provider.embed([_query_embedding_input(query, filters, profile)])[0]
    with Session(phase2_migrated_engine) as current_session:
        _add_graph(current_session, query_vector=query_vector.values)
        current_session.commit()

        candidates = VectorCandidateRetriever(
            current_session,
            provider_registry=EmbeddingProviderRegistry([_embedding_profile()]),
        ).retrieve(query, filters, profile, limit=5)

    assert [candidate.chunk_id for candidate in candidates] == [
        "chunk:expected",
        "chunk:other",
    ]
    assert candidates[0].diagnostics["cosine_distance"] == pytest.approx(
        0.0,
        abs=1e-7,
    )


def _embedding_profile() -> EmbeddingProfileConfig:
    return EmbeddingProfileConfig(
        profile_id="docs_default",
        provider_id="mock",
        model_name="deterministic-docs-default-v1",
        dimensions=3,
        deterministic=True,
    )


class _SpyProvider:
    provider_id = "spy"
    model_id = "spy-model"
    dimensions = 3

    def __init__(self) -> None:
        self.embed_calls = 0

    def embed(self, inputs: Any) -> list[EmbeddingVector]:
        self.embed_calls += 1
        return [
            EmbeddingVector(
                values=[1.0, 0.0, 0.0],
                dimensions=3,
                provider_id=self.provider_id,
                model_id=self.model_id,
            )
            for _input in inputs
        ]


class _SpyRegistry:
    def __init__(self) -> None:
        self.resolve_calls = 0
        self.provider = _SpyProvider()

    def resolve(self, profile_id: str) -> _SpyProvider:
        self.resolve_calls += 1
        return self.provider


def _vector_profile(
    *,
    embedding_profile_id: str = "docs_default",
) -> VectorRetrievalProfile:
    return VectorRetrievalProfile(
        profile_id="docs_vector",
        embedding_profile_id=embedding_profile_id,
        embedding_model_id="embedding-model:mock",
        index_version_id="index-version:test",
        candidate_limit=10,
        hnsw_ef_search=64,
        exact_search_threshold=10,
    )


def _add_graph(session: Session, *, query_vector: list[float]) -> None:
    session.add(
        Source(
            id="source:test",
            config_key="source:test",
            name="Test Source",
            source_type="local_directory",
            source_allowlisted=True,
            sensitivity_class="public",
            license_policy_status="allowed",
            license_id="MIT",
            redaction_status="redacted",
        )
    )
    session.add(
        SourceVersion(
            id="source-version:test",
            source_id="source:test",
            version_label="v1",
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
        Artifact(
            id="artifact:test",
            artifact_key="artifact:test",
            artifact_type="document",
            title="Fixture",
            sanitized_content_hash="sha256:artifact",
            source_id="source:test",
            source_version_id="source-version:test",
            source_type="local_directory",
            source_allowlisted=True,
            visibility_label="invited_users",
            sensitivity_class="public",
            license_policy_status="allowed",
            license_id="MIT",
            redaction_status="redacted",
        )
    )
    session.flush()
    session.add(
        EmbeddingModel(
            id="embedding-model:mock",
            provider_name="mock",
            model_name="deterministic-docs-default-v1",
            provider_model_id="deterministic-docs-default-v1",
            dimensions=3,
            modality="text",
            corpus_scope="docs",
            distance_metric="cosine",
            config_hash="sha256:model",
            deterministic=True,
            promotion_status="mock",
        )
    )
    session.add(
        IndexVersion(
            id="index-version:test",
            name="index-version:test",
            index_kind="vector",
            corpus_scope="docs",
            source_scope={"source_ids": ["source:test"]},
            embedding_model_id="embedding-model:mock",
            vector_profile="docs_default",
            config_hash="sha256:index",
            status="active",
            failure_metadata={},
        )
    )
    session.flush()
    _add_chunk(session, "chunk:expected", "safe vector retrieval", vector=query_vector)
    _add_chunk(
        session,
        "chunk:other",
        "safe unrelated notes",
        vector=[-value for value in query_vector],
    )
    _add_chunk(
        session,
        "chunk:blocked",
        "safe vector retrieval",
        corpus_eligibility_label="prohibited",
        vector=query_vector,
    )


def _add_chunk(
    session: Session,
    chunk_id: str,
    sanitized_text: str,
    *,
    vector: list[float],
    source_id: str = "source:test",
    source_version_id: str = "source-version:test",
    license_policy_status: str = "allowed",
    sensitivity_class: str = "public",
    corpus_eligibility_label: str = "eligible",
    is_current: bool = True,
) -> None:
    session.add(
        Chunk(
            id=chunk_id,
            chunk_key=chunk_id,
            artifact_id="artifact:test",
            sanitized_text=sanitized_text,
            sanitized_content_hash=f"sha256:{chunk_id}",
            artifact_path="docs/reference.md",
            source_id=source_id,
            source_version_id=source_version_id,
            source_type="local_directory",
            source_allowlisted=True,
            visibility_label="invited_users",
            sensitivity_class=sensitivity_class,
            license_policy_status=license_policy_status,
            license_id="MIT",
            redaction_status="redacted",
            corpus_eligibility_label=corpus_eligibility_label,
        )
    )
    session.flush()
    session.add(
        ChunkVersion(
            id=f"chunk-version:{chunk_id}",
            chunk_id=chunk_id,
            source_version_id=source_version_id,
            version_label="v1",
            checksum=f"sha256:{chunk_id}",
            is_current=is_current,
        )
    )
    session.flush()
    session.add(
        Embedding(
            id=f"embedding:{chunk_id}",
            chunk_id=chunk_id,
            embedding_model_id="embedding-model:mock",
            index_version_id="index-version:test",
            sanitized_input_hash=f"sha256:{chunk_id}",
            sanitized_content_hash=f"sha256:{chunk_id}",
            vector=vector,
            dimensions=3,
            distance_metric="cosine",
            is_active=True,
        )
    )
