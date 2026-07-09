from __future__ import annotations

import pytest
from sqlalchemy import Engine, text

from idp_brain.db import assert_pg_search_available

pytestmark = [pytest.mark.integration, pytest.mark.requires_pg_search]


def _insert_bm25_fixture(engine: Engine) -> None:
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
                    'source:bm25-smoke',
                    'bm25-smoke',
                    'BM25 Smoke Source',
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
                    'source-version:bm25-smoke:v1',
                    'source:bm25-smoke',
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
                    'artifact:bm25-smoke:readme',
                    'README.md@v1',
                    'document',
                    'documentation',
                    'README',
                    'markdown',
                    'allowed',
                    'sha256:artifact-bm25',
                    'source:bm25-smoke',
                    'source-version:bm25-smoke:v1',
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
                    heading_path,
                    symbol_path,
                    signature_text,
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
                        'chunk:bm25-smoke:expected',
                        'README.md:1-5@v1',
                        'artifact:bm25-smoke:readme',
                        'Sanitized ParadeDB BM25 retrieval documentation '
                        '[REDACTED_SECRET].',
                        'sha256:chunk-bm25-expected',
                        'Retrieval',
                        'retrieval.bm25',
                        'bm25 smoke',
                        'README.md',
                        'markdown',
                        'documentation',
                        'section',
                        7,
                        'allowed',
                        '[]',
                        '{}',
                        'source:bm25-smoke',
                        'source-version:bm25-smoke:v1',
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
                        'chunk:bm25-smoke:other',
                        'CHANGELOG.md:1-5@v1',
                        'artifact:bm25-smoke:readme',
                        'Sanitized maintenance notes for local database setup.',
                        'sha256:chunk-bm25-other',
                        'Maintenance',
                        'database.setup',
                        'setup smoke',
                        'CHANGELOG.md',
                        'markdown',
                        'documentation',
                        'section',
                        6,
                        'allowed',
                        '[]',
                        '{}',
                        'source:bm25-smoke',
                        'source-version:bm25-smoke:v1',
                        'CHANGELOG.md',
                        'local_directory',
                        true,
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


def test_chunks_bm25_index_returns_sanitized_ids_and_scores(
    phase2_migrated_engine: Engine,
) -> None:
    assert_pg_search_available(phase2_migrated_engine)
    _insert_bm25_fixture(phase2_migrated_engine)

    with phase2_migrated_engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT id, pdb.score(id) AS bm25_score
                FROM chunks
                WHERE sanitized_text ||| :query
                ORDER BY bm25_score DESC, id
                LIMIT 5
                """
            ),
            {"query": "ParadeDB BM25 retrieval"},
        ).all()

    assert rows
    assert rows[0].id == "chunk:bm25-smoke:expected"
    assert rows[0].bm25_score > 0
    assert all("chunk:bm25-smoke" in row.id for row in rows)
