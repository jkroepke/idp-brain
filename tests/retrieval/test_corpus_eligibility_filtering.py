from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from idp_brain.models import Base, IndexVersion
from idp_brain.retrieval.corpus_filters import (
    TrustedCorpusScope,
    build_filtered_chunk_scope,
    narrow_filters,
    post_filter_chunk_count,
    resolve_active_index_filters,
)
from idp_brain.retrieval.models import RetrievalFilterSet


def test_defaults_are_fail_closed_and_caller_hints_are_not_authority() -> None:
    filters = RetrievalFilterSet()
    assert filters.sensitivity_classes == ("public",)
    assert filters.license_ids == ("MIT", "Apache-2.0")
    assert filters.license_policy_statuses == ("allowed",)
    assert "review_required" not in filters.corpus_eligibility_labels
    assert not hasattr(filters, "caller_context_hint")


def test_requested_filters_only_narrow_trusted_policy() -> None:
    trusted = TrustedCorpusScope(source_ids=("source:a", "source:b"))
    narrowed = narrow_filters(
        trusted,
        RetrievalFilterSet(
            source_ids=("source:b", "source:untrusted"),
            sensitivity_classes=("public", "restricted"),
            license_ids=("MIT", "Proprietary"),
        ),
    )
    assert narrowed.source_ids == ("source:b",)
    assert narrowed.sensitivity_classes == ("public",)
    assert narrowed.license_ids == ("MIT",)


def test_disallowed_request_dimension_produces_empty_scope() -> None:
    narrowed = narrow_filters(
        TrustedCorpusScope(), RetrievalFilterSet(sensitivity_classes=("restricted",))
    )
    assert narrowed.sensitivity_classes == ("__no_trusted_match__",)


def test_chunk_scope_contains_every_pre_candidate_exclusion() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        sql = str(
            build_filtered_chunk_scope(
                session, RetrievalFilterSet(), trusted=TrustedCorpusScope()
            )
        )
    engine.dispose()
    for required in (
        "source_allowlisted",
        "source_version_id IS NOT NULL",
        "sanitized_text !=",
        "sensitivity_class IN",
        "license_policy_status IN",
        "license_id IN",
        "redaction_status IN",
        "corpus_eligibility_label IN",
        "chunk_versions.is_current",
        "chunk_versions.tombstoned_at IS NULL",
        "citations.chunk_id = chunks.id",
    ):
        assert required in sql


def test_version_release_time_and_allowlist_filters_are_pushed_down() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    filters = RetrievalFilterSet(
        version_from="v1",
        version_to="v3",
        release_from="v1",
        release_to="v2",
        time_from=datetime(2025, 1, 1, tzinfo=UTC),
        time_to=datetime(2026, 1, 1, tzinfo=UTC),
        source_allowlisted=False,
    )
    with Session(engine) as session:
        sql = str(
            build_filtered_chunk_scope(session, filters, trusted=TrustedCorpusScope())
        )
    engine.dispose()
    assert "version_label >=" in sql and "version_label <=" in sql
    assert "first_seen_at >=" in sql and "first_seen_at <=" in sql
    assert "WHERE" in sql


def test_diagnostics_count_is_post_filter_only() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        scope = build_filtered_chunk_scope(
            session, RetrievalFilterSet(), trusted=TrustedCorpusScope()
        )
        sql = str(post_filter_chunk_count(scope))
    engine.dispose()
    assert "filtered_chunks" in sql
    assert "count(*)" in sql


def test_active_index_resolution_fails_closed_for_absent_inactive_and_mismatch() -> (
    None
):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                IndexVersion(
                    id="inactive",
                    name="inactive",
                    index_kind="vector",
                    corpus_scope="mvp",
                    source_scope={"source_ids": ["s"]},
                    vector_profile="docs",
                    config_hash="x",
                    status="inactive",
                ),
                IndexVersion(
                    id="mismatch",
                    name="mismatch",
                    index_kind="vector",
                    corpus_scope="mvp",
                    source_scope={"source_ids": ["s"]},
                    vector_profile="other",
                    config_hash="y",
                    status="active",
                ),
                IndexVersion(
                    id="wrong-kind",
                    name="wrong-kind",
                    index_kind="bm25",
                    corpus_scope="mvp",
                    source_scope={"source_ids": ["s"]},
                    bm25_profile="docs",
                    config_hash="z",
                    status="active",
                ),
                IndexVersion(
                    id="active",
                    name="active",
                    index_kind="vector",
                    corpus_scope="mvp",
                    source_scope={"source_ids": ["trusted"]},
                    vector_profile="docs",
                    config_hash="a",
                    status="active",
                ),
            ]
        )
        session.flush()
        for index_id in ("missing", "inactive", "mismatch", "wrong-kind"):
            resolved = resolve_active_index_filters(
                session,
                RetrievalFilterSet(active_index_version_id=index_id),
                required=True,
                expected_kind="vector",
                expected_profile="docs",
            )
            assert resolved.source_ids == ("__no_active_index__",)
        narrowed = resolve_active_index_filters(
            session,
            RetrievalFilterSet(
                active_index_version_id="active",
                source_ids=("trusted", "outside"),
            ),
            required=True,
            expected_kind="vector",
            expected_profile="docs",
        )
        assert narrowed.source_ids == ("trusted",)
    engine.dispose()
