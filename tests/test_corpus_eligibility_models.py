from __future__ import annotations

import pytest
from sqlalchemy import CheckConstraint, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from idp_brain.models import (
    ALLOWED_RETRIEVABLE_LICENSE_IDS,
    DEFAULT_LICENSE_POLICY_STATUS,
    DEFAULT_REDACTION_STATUS,
    DEFAULT_SENSITIVITY_CLASS,
    DEFAULT_SOURCE_ALLOWLISTED,
    DEFAULT_VISIBILITY_LABEL,
    Artifact,
    Base,
    Chunk,
    Citation,
    Claim,
    CorpusPolicyDefault,
    Fact,
    Relationship,
    Source,
    SourceVersion,
)

ELIGIBILITY_TABLES = (
    Source,
    SourceVersion,
    Artifact,
    Chunk,
    Citation,
    Fact,
    Claim,
    Relationship,
)
ELIGIBILITY_COLUMNS = {
    "source_allowlisted",
    "visibility_label",
    "sensitivity_class",
    "license_policy_status",
    "license_id",
    "redaction_status",
}


def test_corpus_policy_defaults_are_global_and_fail_closed() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            defaults = CorpusPolicyDefault(id="global", policy_version="mvp-2.4")
            session.add(defaults)
            session.flush()

            assert defaults.source_allowlist_default is DEFAULT_SOURCE_ALLOWLISTED
            assert defaults.allowed_license_ids == list(ALLOWED_RETRIEVABLE_LICENSE_IDS)
            assert defaults.allowed_license_policy_statuses == ["allowed"]
            assert defaults.allowed_sensitivity_classes == ["public"]
            assert defaults.allowed_visibility_labels == [DEFAULT_VISIBILITY_LABEL]
            assert defaults.allowed_redaction_statuses == ["not_required", "redacted"]
    finally:
        engine.dispose()


def test_retrievable_and_citable_records_default_to_fail_closed_labels() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            source = Source(
                id="source:default",
                config_key="default-source",
                name="Default Source",
                source_type="git",
            )
            session.add(source)
            session.flush()

            assert source.source_allowlisted is DEFAULT_SOURCE_ALLOWLISTED
            assert source.visibility_label == DEFAULT_VISIBILITY_LABEL
            assert source.sensitivity_class == DEFAULT_SENSITIVITY_CLASS
            assert source.license_policy_status == DEFAULT_LICENSE_POLICY_STATUS
            assert source.license_id is None
            assert source.redaction_status == DEFAULT_REDACTION_STATUS
    finally:
        engine.dispose()


def test_mit_and_apache_are_the_only_allowed_retrievable_mvp_license_ids() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    Source(
                        id="source:mit",
                        config_key="mit-source",
                        name="MIT Source",
                        source_type="git",
                        source_allowlisted=True,
                        sensitivity_class="public",
                        license_policy_status="allowed",
                        license_id="MIT",
                        redaction_status="not_required",
                    ),
                    Source(
                        id="source:apache",
                        config_key="apache-source",
                        name="Apache Source",
                        source_type="git",
                        source_allowlisted=True,
                        sensitivity_class="public",
                        license_policy_status="allowed",
                        license_id="Apache-2.0",
                        redaction_status="redacted",
                    ),
                ]
            )
            session.flush()

            session.add(
                Source(
                    id="source:gpl",
                    config_key="gpl-source",
                    name="GPL Source",
                    source_type="git",
                    source_allowlisted=True,
                    sensitivity_class="public",
                    license_policy_status="allowed",
                    license_id="GPL-3.0",
                    redaction_status="not_required",
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
    finally:
        engine.dispose()


def test_unknown_or_review_required_licenses_must_fail_closed_without_license_id() -> (
    None
):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                Source(
                    id="source:unknown",
                    config_key="unknown-source",
                    name="Unknown Source",
                    source_type="git",
                    license_policy_status="unknown",
                    license_id=None,
                )
            )
            session.flush()

            session.add(
                Source(
                    id="source:unknown-with-license",
                    config_key="unknown-with-license-source",
                    name="Unknown With License Source",
                    source_type="git",
                    license_policy_status="unknown",
                    license_id="MIT",
                )
            )
            session.flush()

            session.add(
                Source(
                    id="source:allowed-without-license",
                    config_key="allowed-without-license-source",
                    name="Allowed Without License Source",
                    source_type="git",
                    license_policy_status="allowed",
                    license_id=None,
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
    finally:
        engine.dispose()


def test_required_corpus_labels_exist_on_facts_and_retrievable_records() -> None:
    for model in ELIGIBILITY_TABLES:
        columns = set(model.__table__.columns.keys())
        assert ELIGIBILITY_COLUMNS <= columns

        for column_name in ELIGIBILITY_COLUMNS - {"license_id"}:
            assert model.__table__.c[column_name].nullable is False


def test_constraints_and_indexes_support_future_pre_subquery_filter_pushdown() -> None:
    # Later retrieval must apply source allowlist, license, sensitivity, redaction,
    # version, and active-index filters before exact lookup, BM25, vector search,
    # relationship traversal, memory lookup, diagnostics, CLI output, and MCP
    # search/fetch. This test only verifies the schema contract for that future
    # behavior; it does not implement retrieval.
    for model in ELIGIBILITY_TABLES:
        table = model.__table__
        index_names = {index.name for index in table.indexes}
        constraint_text = " ".join(
            str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )

        assert f"ix_{table.name}_filter_pushdown" in index_names
        assert f"ix_{table.name}_license_id" in index_names
        assert "license_policy_status" in constraint_text
        assert "MIT" in constraint_text
        assert "Apache-2.0" in constraint_text
        assert "invited_users" in constraint_text
        assert "redaction_status" in constraint_text

    for table_name in {
        "artifact_versions",
        "chunk_versions",
        "fact_versions",
        "claim_versions",
        "relationship_versions",
    }:
        version_index_names = {
            index.name for index in Base.metadata.tables[table_name].indexes
        }
        assert f"ix_{table_name}_active_version_filter" in version_index_names


def test_schema_does_not_introduce_per_caller_retrieval_policy_tables() -> None:
    forbidden_fragments = ("caller", "principal", "role", "permission", "tenant")
    policy_table_names = {
        table_name
        for table_name in Base.metadata.tables
        if "policy" in table_name or "eligibility" in table_name
    }

    assert policy_table_names == {"corpus_policy_defaults"}
    assert not any(
        fragment in table_name
        for table_name in Base.metadata.tables
        for fragment in forbidden_fragments
    )
