from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.db import MigrationCheckError
from idp_brain.models import Base, Chunk, ChunkVersion, IndexVersion
from idp_brain.retrieval import (
    BM25CandidateRetriever,
    BM25RetrievalProfile,
    RetrievalFilters,
    RetrievalQuery,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False, future=True)
    with factory() as current_session:
        yield current_session
    engine.dispose()


def test_bm25_fallback_returns_metadata_only(session: Session) -> None:
    _add_chunk(
        session,
        chunk_id="chunk:expected",
        sanitized_text="safe bm25 retrieval guide",
        heading_path="Retrieval",
    )
    session.commit()

    candidates = BM25CandidateRetriever(
        session,
        deterministic_fallback=True,
    ).retrieve(
        RetrievalQuery(query_text="bm25"),
        RetrievalFilters(source_ids=("src:docs",)),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:expected"]
    candidate = candidates[0]
    assert candidate.retrieval_path == "bm25"
    assert candidate.rank == 1
    assert candidate.diagnostics["bm25_score"] == 1.0
    assert candidate.metadata["artifact_path"] == "docs/reference.md"
    assert "sanitized_text" not in candidate.metadata
    assert "raw_text" not in candidate.model_dump_json()


def test_bm25_profile_limits_search_to_configured_safe_fields(
    session: Session,
) -> None:
    _add_chunk(
        session,
        chunk_id="chunk:text",
        sanitized_text="safe profile query text",
        artifact_path="docs/reference.md",
    )
    _add_chunk(
        session,
        chunk_id="chunk:path",
        sanitized_text="safe unrelated text",
        artifact_path="docs/profile-query.md",
    )
    session.commit()

    candidates = BM25CandidateRetriever(
        session,
        deterministic_fallback=True,
    ).retrieve(
        RetrievalQuery(query_text="profile-query"),
        RetrievalFilters(source_ids=("src:docs",)),
        BM25RetrievalProfile(bm25_fields=("artifact_path",)),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:path"]
    assert candidates[0].matched_fields == ("artifact_path",)
    with pytest.raises(ValueError, match="Unsupported BM25 field"):
        BM25RetrievalProfile(bm25_fields=("raw_text",))


def test_bm25_filters_apply_before_matching_by_default(session: Session) -> None:
    _add_chunk(session, chunk_id="chunk:allowed", sanitized_text="safe bm25 term")
    _add_chunk(
        session,
        chunk_id="chunk:denied-license",
        sanitized_text="safe bm25 term",
        license_policy_status="denied",
    )
    _add_chunk(
        session,
        chunk_id="chunk:restricted",
        sanitized_text="safe bm25 term",
        sensitivity_class="restricted",
    )
    _add_chunk(
        session,
        chunk_id="chunk:prohibited",
        sanitized_text="safe bm25 term",
        corpus_eligibility_label="prohibited",
    )
    session.commit()

    candidates = BM25CandidateRetriever(
        session,
        deterministic_fallback=True,
    ).retrieve(
        RetrievalQuery(query_text="bm25"),
        RetrievalFilters(),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:allowed"]


def test_bm25_active_index_scope_filters_sources(session: Session) -> None:
    _add_chunk(
        session,
        chunk_id="chunk:in",
        source_id="src:in",
        sanitized_text="safe bm25 term",
    )
    _add_chunk(
        session,
        chunk_id="chunk:out",
        source_id="src:out",
        sanitized_text="safe bm25 term",
    )
    session.add(
        IndexVersion(
            id="idx:bm25",
            name="bm25-active",
            index_kind="bm25",
            corpus_scope="mvp",
            source_scope={"source_ids": ["src:in"]},
            config_hash="hash",
            status="active",
        )
    )
    session.commit()

    candidates = BM25CandidateRetriever(
        session,
        deterministic_fallback=True,
    ).retrieve(
        RetrievalQuery(query_text="bm25"),
        RetrievalFilters(active_index_version_id="idx:bm25"),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:in"]


def test_bm25_fallback_orders_ties_by_chunk_id(session: Session) -> None:
    _add_chunk(session, chunk_id="chunk:b", sanitized_text="safe bm25 term")
    _add_chunk(session, chunk_id="chunk:a", sanitized_text="safe bm25 term")
    session.commit()

    candidates = BM25CandidateRetriever(
        session,
        deterministic_fallback=True,
    ).retrieve(
        RetrievalQuery(query_text="bm25"),
        RetrievalFilters(source_ids=("src:docs",)),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:a", "chunk:b"]


def test_bm25_fails_clearly_without_pg_search_or_test_fallback(
    session: Session,
) -> None:
    _add_chunk(session, chunk_id="chunk:expected", sanitized_text="safe bm25 term")
    session.commit()

    with pytest.raises(MigrationCheckError, match="pg_search"):
        BM25CandidateRetriever(session).retrieve(
            RetrievalQuery(query_text="bm25"),
            RetrievalFilters(source_ids=("src:docs",)),
        )


def _add_chunk(
    session: Session,
    *,
    chunk_id: str,
    source_id: str = "src:docs",
    source_version_id: str = "sv:docs",
    source_type: str = "local_directory",
    version_label: str = "v1.0.0",
    artifact_path: str = "docs/reference.md",
    heading_path: str | None = None,
    symbol_path: str | None = None,
    signature_text: str | None = None,
    sanitized_text: str = "safe bm25 docs",
    sensitivity_class: str = "public",
    license_policy_status: str = "allowed",
    redaction_status: str = "redacted",
    corpus_eligibility_label: str = "eligible",
) -> None:
    session.add(
        Chunk(
            id=chunk_id,
            chunk_key=chunk_id,
            artifact_id=f"artifact:{chunk_id}",
            extraction_id=None,
            source_id=source_id,
            source_version_id=source_version_id,
            source_type=source_type,
            version_label=version_label,
            artifact_path=artifact_path,
            path=artifact_path,
            structure_path=[],
            heading_path=heading_path,
            symbol_path=symbol_path,
            signature_text=signature_text,
            language="markdown",
            artifact_role="docs",
            chunk_kind="section",
            sanitized_text=sanitized_text,
            sanitized_content_hash=f"hash:{chunk_id}",
            source_allowlisted=True,
            visibility_label="invited_users",
            sensitivity_class=sensitivity_class,
            license_policy_status=license_policy_status,
            license_id="MIT",
            redaction_status=redaction_status,
            corpus_eligibility_label=corpus_eligibility_label,
        )
    )
    session.add(
        ChunkVersion(
            id=f"chunk-version:{chunk_id}",
            chunk_id=chunk_id,
            source_version_id=source_version_id,
            version_label=version_label,
            is_current=True,
        )
    )
