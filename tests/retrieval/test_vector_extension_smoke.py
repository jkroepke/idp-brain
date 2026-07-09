from __future__ import annotations

import pytest
from sqlalchemy import Engine, text

from idp_brain.db import assert_vector_available

pytestmark = [pytest.mark.integration, pytest.mark.requires_pgvector]


def _vector32(first: float = 0.0, second: float = 0.0) -> str:
    values = [0.0] * 32
    values[0] = first
    values[1] = second
    return "[" + ",".join(str(value) for value in values) + "]"


def _insert_vector_fixture(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO sources (
                    id,
                    config_key,
                    name,
                    source_type,
                    source_allowlisted,
                    visibility_label,
                    sensitivity_class,
                    license_policy_status,
                    license_id,
                    redaction_status
                )
                VALUES (
                    'source:vector-smoke',
                    'vector-smoke',
                    'Vector Smoke Source',
                    'local_directory',
                    true,
                    'invited_users',
                    'public',
                    'allowed',
                    'MIT',
                    'redacted'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO source_versions (
                    id,
                    source_id,
                    version_label,
                    is_current,
                    source_allowlisted,
                    visibility_label,
                    sensitivity_class,
                    license_policy_status,
                    license_id,
                    redaction_status
                )
                VALUES (
                    'source-version:vector-smoke:v1',
                    'source:vector-smoke',
                    'v1',
                    true,
                    true,
                    'invited_users',
                    'public',
                    'allowed',
                    'MIT',
                    'redacted'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO artifacts (
                    id,
                    artifact_key,
                    artifact_type,
                    artifact_role,
                    title,
                    language,
                    corpus_eligibility_label,
                    sanitized_content_hash,
                    source_id,
                    source_version_id,
                    path,
                    source_type,
                    source_allowlisted,
                    visibility_label,
                    sensitivity_class,
                    license_policy_status,
                    license_id,
                    redaction_status
                )
                VALUES (
                    'artifact:vector-smoke:readme',
                    'README.md@v1',
                    'document',
                    'documentation',
                    'README',
                    'markdown',
                    'allowed',
                    'sha256:artifact-vector',
                    'source:vector-smoke',
                    'source-version:vector-smoke:v1',
                    'README.md',
                    'local_directory',
                    true,
                    'invited_users',
                    'public',
                    'allowed',
                    'MIT',
                    'redacted'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO chunks (
                    id,
                    chunk_key,
                    artifact_id,
                    sanitized_text,
                    sanitized_content_hash,
                    artifact_path,
                    language,
                    artifact_role,
                    chunk_kind,
                    token_count,
                    corpus_eligibility_label,
                    structure_path,
                    metadata,
                    source_id,
                    source_version_id,
                    path,
                    source_type,
                    source_allowlisted,
                    visibility_label,
                    sensitivity_class,
                    license_policy_status,
                    license_id,
                    redaction_status,
                    version_label
                )
                VALUES
                    (
                        'chunk:vector-smoke:expected',
                        'README.md:1-5@v1',
                        'artifact:vector-smoke:readme',
                        'Sanitized pgvector retrieval documentation.',
                        'sha256:chunk-vector-expected',
                        'README.md',
                        'markdown',
                        'documentation',
                        'section',
                        5,
                        'allowed',
                        '[]',
                        '{}',
                        'source:vector-smoke',
                        'source-version:vector-smoke:v1',
                        'README.md',
                        'local_directory',
                        true,
                        'invited_users',
                        'public',
                        'allowed',
                        'MIT',
                        'redacted',
                        'v1'
                    ),
                    (
                        'chunk:vector-smoke:other',
                        'OTHER.md:1-5@v1',
                        'artifact:vector-smoke:readme',
                        'Sanitized unrelated local database notes.',
                        'sha256:chunk-vector-other',
                        'OTHER.md',
                        'markdown',
                        'documentation',
                        'section',
                        5,
                        'allowed',
                        '[]',
                        '{}',
                        'source:vector-smoke',
                        'source-version:vector-smoke:v1',
                        'OTHER.md',
                        'local_directory',
                        true,
                        'invited_users',
                        'public',
                        'allowed',
                        'MIT',
                        'redacted',
                        'v1'
                    ),
                    (
                        'chunk:vector-smoke:blocked',
                        'BLOCKED.md:1-5@v1',
                        'artifact:vector-smoke:readme',
                        'Sanitized but not corpus-eligible.',
                        'sha256:chunk-vector-blocked',
                        'BLOCKED.md',
                        'markdown',
                        'documentation',
                        'section',
                        5,
                        'blocked',
                        '[]',
                        '{}',
                        'source:vector-smoke',
                        'source-version:vector-smoke:v1',
                        'BLOCKED.md',
                        'local_directory',
                        false,
                        'invited_users',
                        'public',
                        'allowed',
                        'MIT',
                        'redacted',
                        'v1'
                    )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO embedding_models (
                    id,
                    provider_name,
                    model_name,
                    provider_model_id,
                    dimensions,
                    modality,
                    corpus_scope,
                    distance_metric,
                    config_hash,
                    deterministic,
                    external_calls_allowed,
                    promotion_status
                )
                VALUES (
                    'embedding-model:vector-smoke',
                    'mock',
                    'deterministic-docs-default-v1',
                    'deterministic-docs-default-v1',
                    32,
                    'text',
                    'docs',
                    'cosine',
                    'sha256:model-vector-smoke',
                    true,
                    false,
                    'mock'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO index_versions (
                    id,
                    name,
                    index_kind,
                    corpus_scope,
                    source_scope,
                    embedding_model_id,
                    vector_profile,
                    config_hash,
                    status,
                    failure_metadata
                )
                VALUES (
                    'index-version:vector-smoke',
                    'index-version:vector-smoke',
                    'vector',
                    'docs',
                    '{"source_ids":["source:vector-smoke"]}',
                    'embedding-model:vector-smoke',
                    'docs_default',
                    'sha256:index-vector-smoke',
                    'active',
                    '{}'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO embeddings (
                    id,
                    chunk_id,
                    embedding_model_id,
                    index_version_id,
                    sanitized_input_hash,
                    sanitized_content_hash,
                    vector,
                    dimensions,
                    distance_metric,
                    is_active
                )
                VALUES
                    (
                        'embedding:vector-smoke:expected',
                        'chunk:vector-smoke:expected',
                        'embedding-model:vector-smoke',
                        'index-version:vector-smoke',
                        'sha256:chunk-vector-expected',
                        'sha256:chunk-vector-expected',
                        CAST(:expected_vector AS vector),
                        32,
                        'cosine',
                        true
                    ),
                    (
                        'embedding:vector-smoke:other',
                        'chunk:vector-smoke:other',
                        'embedding-model:vector-smoke',
                        'index-version:vector-smoke',
                        'sha256:chunk-vector-other',
                        'sha256:chunk-vector-other',
                        CAST(:other_vector AS vector),
                        32,
                        'cosine',
                        true
                    ),
                    (
                        'embedding:vector-smoke:blocked',
                        'chunk:vector-smoke:blocked',
                        'embedding-model:vector-smoke',
                        'index-version:vector-smoke',
                        'sha256:chunk-vector-blocked',
                        'sha256:chunk-vector-blocked',
                        CAST(:blocked_vector AS vector),
                        32,
                        'cosine',
                        true
                    )
                """
            ),
            {
                "expected_vector": _vector32(second=1.0),
                "other_vector": _vector32(first=1.0),
                "blocked_vector": _vector32(second=1.0),
            },
        )


def test_vector_distance_orders_joined_active_sanitized_chunks(
    phase2_migrated_engine: Engine,
) -> None:
    assert_vector_available(phase2_migrated_engine)
    _insert_vector_fixture(phase2_migrated_engine)

    with phase2_migrated_engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT c.id, e.vector <=> CAST(:query_vector AS vector) AS distance
                FROM embeddings e
                JOIN chunks c ON c.id = e.chunk_id
                WHERE e.is_active
                AND e.embedding_model_id = 'embedding-model:vector-smoke'
                AND e.index_version_id = 'index-version:vector-smoke'
                AND c.source_allowlisted
                AND c.visibility_label = 'invited_users'
                AND c.sensitivity_class IN ('public', 'internal')
                AND c.license_policy_status = 'allowed'
                AND c.redaction_status = 'redacted'
                AND c.corpus_eligibility_label = 'allowed'
                AND c.source_version_id IS NOT NULL
                ORDER BY e.vector <=> CAST(:query_vector AS vector), c.id
                LIMIT 5
                """
            ),
            {"query_vector": _vector32(second=1.0)},
        ).all()

    assert [row.id for row in rows] == [
        "chunk:vector-smoke:expected",
        "chunk:vector-smoke:other",
    ]
    assert rows[0].distance == pytest.approx(0.0)
    assert rows[1].distance > rows[0].distance
