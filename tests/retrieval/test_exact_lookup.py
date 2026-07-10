from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from idp_brain.models import Base, Chunk, ChunkVersion, IndexVersion
from idp_brain.retrieval import ExactLookupRetriever, RetrievalFilters, RetrievalQuery
from idp_brain.retrieval.profiles import ExactRetrievalProfile


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False, future=True)
    with factory() as session:
        yield session
    engine.dispose()


def test_exact_lookup_returns_sanitized_candidate_metadata_only(
    session: Session,
) -> None:
    _add_chunk(
        session,
        chunk_id="chunk:widget",
        symbol_path="Widget.render",
        signature_text="def render(self) -> str",
        sanitized_text="safe rendered widget documentation",
    )
    session.commit()

    candidates = ExactLookupRetriever(session).retrieve(
        RetrievalQuery(query_text="Widget.render"),
        RetrievalFilters(
            source_ids=("src:docs",),
            visibility_labels=("invited_users",),
            sensitivity_classes=("public",),
            license_policy_statuses=("allowed",),
            corpus_eligibility_labels=("eligible",),
        ),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:widget"]
    candidate = candidates[0]
    assert candidate.retrieval_path == "exact"
    assert candidate.matched_fields == ("symbol_path",)
    assert candidate.metadata["symbol_path"] == "Widget.render"
    assert candidate.metadata["artifact_path"] == "docs/reference.md"
    assert "sanitized_text" not in candidate.metadata
    assert "raw_text" not in candidate.model_dump_json()


def test_exact_lookup_matches_paths_schema_versions_and_errors(
    session: Session,
) -> None:
    _add_chunk(
        session,
        chunk_id="chunk:path",
        artifact_path="openapi/users.yaml",
        structure_path=["paths", "/v1/users", "get"],
        sanitized_text="safe endpoint chunk",
    )
    _add_chunk(
        session,
        chunk_id="chunk:version",
        version_label="v2.4.1",
        sanitized_text="safe release notes",
    )
    _add_chunk(
        session,
        chunk_id="chunk:error",
        signature_text="raises CONFIG_TIMEOUT",
        sanitized_text="safe CONFIG_TIMEOUT diagnostic",
    )
    session.commit()
    retriever = ExactLookupRetriever(session)
    filters = RetrievalFilters(source_ids=("src:docs",))

    assert [
        candidate.chunk_id
        for candidate in retriever.retrieve(
            RetrievalQuery(query_text="/v1/users"),
            filters,
        )
    ] == ["chunk:path"]
    assert [
        candidate.chunk_id
        for candidate in retriever.retrieve(
            RetrievalQuery(query_text="v2.4.1"), filters
        )
    ] == ["chunk:version"]
    assert [
        candidate.chunk_id
        for candidate in retriever.retrieve(
            RetrievalQuery(query_text="CONFIG_TIMEOUT"),
            filters,
        )
    ] == ["chunk:error"]


def test_exact_lookup_uses_profile_metadata_fields(session: Session) -> None:
    _add_chunk(
        session,
        chunk_id="chunk:endpoint",
        sanitized_text="safe endpoint docs",
        metadata={"endpoint_path": "GET /v1/users", "schema_key": "UserList"},
    )
    session.commit()

    candidates = ExactLookupRetriever(session).retrieve(
        RetrievalQuery(query_text="/v1/users"),
        RetrievalFilters(source_ids=("src:docs",)),
        ExactRetrievalProfile(
            profile_id="api_symbol_lookup",
            exact_fields=("endpoint_path", "schema_key"),
            candidate_limit=10,
        ),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:endpoint"]
    assert candidates[0].matched_fields == ("endpoint_path",)


def test_exact_lookup_respects_profile_field_allowlist(session: Session) -> None:
    _add_chunk(
        session,
        chunk_id="chunk:symbol",
        symbol_path="Widget.render",
        metadata={"endpoint_path": "Widget.render"},
    )
    _add_chunk(
        session,
        chunk_id="chunk:symbol-only",
        symbol_path="Widget.render",
    )
    session.commit()

    candidates = ExactLookupRetriever(session).retrieve(
        RetrievalQuery(query_text="Widget.render"),
        RetrievalFilters(source_ids=("src:docs",)),
        ExactRetrievalProfile(
            profile_id="metadata_only",
            exact_fields=("endpoint_path",),
            candidate_limit=10,
        ),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:symbol"]
    assert candidates[0].matched_fields == ("endpoint_path",)


def test_exact_lookup_profile_can_require_active_index_filter(
    session: Session,
) -> None:
    with pytest.raises(ValueError, match="active_index_version"):
        ExactLookupRetriever(session).retrieve(
            RetrievalQuery(query_text="Widget.render"),
            RetrievalFilters(source_ids=("src:docs",)),
            ExactRetrievalProfile(
                profile_id="api_symbol_lookup",
                exact_fields=("symbol_path",),
                candidate_limit=10,
                require_active_index=True,
            ),
        )


def test_filters_are_applied_before_exact_lookup(session: Session) -> None:
    _add_chunk(session, chunk_id="chunk:allowed", symbol_path="Config.load")
    _add_chunk(
        session,
        chunk_id="chunk:blocked-source",
        source_id="src:blocked",
        symbol_path="Config.load",
    )
    _add_chunk(
        session,
        chunk_id="chunk:blocked-license",
        symbol_path="Config.load",
        license_policy_status="denied",
    )
    _add_chunk(
        session,
        chunk_id="chunk:blocked-redaction",
        symbol_path="Config.load",
        redaction_status="unknown",
    )
    _add_chunk(
        session,
        chunk_id="chunk:blocked-sensitivity",
        symbol_path="Config.load",
        sensitivity_class="restricted",
    )
    _add_chunk(
        session,
        chunk_id="chunk:blocked-corpus",
        symbol_path="Config.load",
        corpus_eligibility_label="prohibited",
    )
    session.commit()

    candidates = ExactLookupRetriever(session).retrieve(
        RetrievalQuery(query_text="Config.load"),
        RetrievalFilters(
            source_ids=("src:docs",),
            sensitivity_classes=("public",),
            license_policy_statuses=("allowed",),
            redaction_statuses=("redacted",),
        ),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:allowed"]


def test_default_policy_filters_exclude_disallowed_exact_matches(
    session: Session,
) -> None:
    _add_chunk(session, chunk_id="chunk:allowed", symbol_path="Config.load")
    _add_chunk(
        session,
        chunk_id="chunk:denied-license",
        symbol_path="Config.load",
        license_policy_status="denied",
    )
    _add_chunk(
        session,
        chunk_id="chunk:restricted",
        symbol_path="Config.load",
        sensitivity_class="restricted",
    )
    _add_chunk(
        session,
        chunk_id="chunk:prohibited",
        symbol_path="Config.load",
        corpus_eligibility_label="prohibited",
    )
    session.commit()

    candidates = ExactLookupRetriever(session).retrieve(
        RetrievalQuery(query_text="Config.load"),
        RetrievalFilters(),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:allowed"]


def test_policy_filters_apply_before_fuzzy_lookup_by_default(
    session: Session,
) -> None:
    _add_chunk(session, chunk_id="chunk:allowed", symbol_path="ConfigurationLoader")
    _add_chunk(
        session,
        chunk_id="chunk:denied-license",
        symbol_path="ConfigurationLoader",
        license_policy_status="denied",
    )
    _add_chunk(
        session,
        chunk_id="chunk:restricted",
        symbol_path="ConfigurationLoader",
        sensitivity_class="restricted",
    )
    _add_chunk(
        session,
        chunk_id="chunk:prohibited",
        symbol_path="ConfigurationLoader",
        corpus_eligibility_label="prohibited",
    )
    session.commit()

    candidates = ExactLookupRetriever(session).retrieve(
        RetrievalQuery(query_text="Configuration", enable_fuzzy=True),
        RetrievalFilters(),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:allowed"]
    assert candidates[0].retrieval_path == "fuzzy"


def test_active_index_version_scope_filters_sources(session: Session) -> None:
    _add_chunk(
        session, chunk_id="chunk:in", source_id="src:in", symbol_path="Config.load"
    )
    _add_chunk(
        session,
        chunk_id="chunk:out",
        source_id="src:out",
        symbol_path="Config.load",
    )
    session.add(
        IndexVersion(
            id="idx:exact",
            name="exact-active",
            index_kind="exact",
            corpus_scope="mvp",
            source_scope={"source_ids": ["src:in"]},
            config_hash="hash",
            status="active",
        )
    )
    session.commit()

    candidates = ExactLookupRetriever(session).retrieve(
        RetrievalQuery(query_text="Config.load"),
        RetrievalFilters(active_index_version_id="idx:exact"),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:in"]


def test_fuzzy_lookup_is_disabled_unless_requested(session: Session) -> None:
    _add_chunk(session, chunk_id="chunk:fuzzy", symbol_path="ConfigurationLoader")
    session.commit()
    retriever = ExactLookupRetriever(session)
    filters = RetrievalFilters(source_ids=("src:docs",))

    assert retriever.retrieve(RetrievalQuery(query_text="Configuration"), filters) == []
    fuzzy = retriever.retrieve(
        RetrievalQuery(query_text="Configuration", enable_fuzzy=True),
        filters,
    )

    assert [candidate.chunk_id for candidate in fuzzy] == ["chunk:fuzzy"]
    assert fuzzy[0].retrieval_path == "fuzzy"


def test_exact_lookup_ordering_is_deterministic(session: Session) -> None:
    _add_chunk(
        session,
        chunk_id="chunk:b",
        artifact_path="docs/reference/deep/path.md",
        symbol_path="Config.load",
    )
    _add_chunk(
        session,
        chunk_id="chunk:a",
        artifact_path="docs/api.md",
        symbol_path="Config.load",
    )
    session.commit()

    candidates = ExactLookupRetriever(session).retrieve(
        RetrievalQuery(query_text="Config.load"),
        RetrievalFilters(source_ids=("src:docs",)),
    )

    assert [candidate.chunk_id for candidate in candidates] == ["chunk:b", "chunk:a"]


def _add_chunk(
    session: Session,
    *,
    chunk_id: str,
    source_id: str = "src:docs",
    source_version_id: str = "sv:docs",
    source_type: str = "local_directory",
    version_label: str = "v1.0.0",
    artifact_path: str = "docs/reference.md",
    structure_path: list[str] | None = None,
    heading_path: str | None = None,
    symbol_path: str | None = None,
    signature_text: str | None = None,
    sanitized_text: str = "safe Config.load docs",
    metadata: dict[str, str] | None = None,
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
            structure_path=structure_path or [],
            heading_path=heading_path,
            symbol_path=symbol_path,
            signature_text=signature_text,
            language="python",
            artifact_role="docs",
            chunk_kind="section",
            sanitized_text=sanitized_text,
            sanitized_content_hash=f"hash:{chunk_id}",
            metadata_=metadata or {},
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
