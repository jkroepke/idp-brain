from __future__ import annotations

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from idp_brain.db import assert_pg_search_available
from idp_brain.retrieval import (
    BM25CandidateRetriever as _BM25CandidateRetriever,
)
from idp_brain.retrieval import (
    BM25RetrievalProfile,
    RetrievalFilters,
    RetrievalQuery,
)
from idp_brain.retrieval.corpus_filters import TrustedCorpusScope


def BM25CandidateRetriever(session: Session) -> _BM25CandidateRetriever:
    return _BM25CandidateRetriever(session, trusted_scope=TrustedCorpusScope())


pytestmark = [pytest.mark.integration, pytest.mark.requires_pg_search]


def test_bm25_retriever_returns_scored_sanitized_candidates(
    phase2_migrated_engine: Engine,
) -> None:
    assert_pg_search_available(phase2_migrated_engine)
    _insert_bm25_fixture(phase2_migrated_engine)

    with Session(phase2_migrated_engine) as session:
        candidates = BM25CandidateRetriever(session).retrieve(
            RetrievalQuery(query_text="ParadeDB BM25 retrieval"),
            RetrievalFilters(
                source_ids=("source:bm25-retriever",),
                active_index_version_id="index:bm25-retriever",
            ),
            BM25RetrievalProfile(
                profile_id="bm25_integration",
                bm25_fields=("sanitized_text", "heading_path", "artifact_path"),
            ),
            limit=50,
        )

    assert [candidate.chunk_id for candidate in candidates] == [
        "chunk:bm25-retriever:expected"
    ]
    assert candidates[0].retrieval_path == "bm25"
    assert candidates[0].diagnostics["bm25_score"] > 0
    assert "sanitized_text" not in candidates[0].metadata
    assert "raw_text" not in candidates[0].model_dump_json()


def _insert_bm25_fixture(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO sources (
                    id, config_key, name, source_type, source_allowlisted,
                    visibility_label, sensitivity_class, license_policy_status,
                    license_id, redaction_status
                )
                VALUES (
                    'source:bm25-retriever', 'bm25-retriever',
                    'BM25 Retriever Source', 'local_directory', true,
                    'invited_users', 'public', 'allowed', 'MIT', 'redacted'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO index_versions (
                    id, name, index_kind, corpus_scope, source_scope,
                    bm25_profile, config_hash, status, failure_metadata
                ) VALUES (
                    'index:bm25-retriever', 'bm25-retriever', 'bm25', 'mvp',
                    '{"source_ids":["source:bm25-retriever"]}',
                    'bm25_integration', 'fixture', 'active', '{}'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO source_versions (
                    id, source_id, version_label, is_current,
                    source_allowlisted, visibility_label, sensitivity_class,
                    license_policy_status, license_id, redaction_status
                )
                VALUES (
                    'source-version:bm25-retriever:v1',
                    'source:bm25-retriever', 'v1', true, true,
                    'invited_users', 'public', 'allowed', 'MIT', 'redacted'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO artifacts (
                    id, artifact_key, artifact_type, artifact_role, title,
                    language, corpus_eligibility_label, sanitized_content_hash,
                    source_id, source_version_id, path, source_type,
                    source_allowlisted, visibility_label, sensitivity_class,
                    license_policy_status, license_id, redaction_status
                )
                VALUES (
                    'artifact:bm25-retriever:readme', 'README.md@v1',
                    'document', 'documentation', 'README', 'markdown',
                    'allowed', 'sha256:artifact-bm25-retriever',
                    'source:bm25-retriever',
                    'source-version:bm25-retriever:v1', 'README.md',
                    'local_directory', true, 'invited_users', 'public',
                    'allowed', 'MIT', 'redacted'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO chunks (
                    id, chunk_key, artifact_id, sanitized_text,
                    sanitized_content_hash, heading_path, symbol_path,
                    signature_text, artifact_path, language, artifact_role,
                    chunk_kind, token_count, corpus_eligibility_label,
                    structure_path, metadata, source_id, source_version_id,
                    path, source_type, source_allowlisted, visibility_label,
                    sensitivity_class, license_policy_status, license_id,
                    redaction_status, version_label
                )
                VALUES
                    (
                        'chunk:bm25-retriever:expected',
                        'README.md:1-5@v1',
                        'artifact:bm25-retriever:readme',
                        'Sanitized ParadeDB BM25 retrieval documentation.',
                        'sha256:chunk-bm25-expected', 'Retrieval',
                        'retrieval.bm25', 'bm25 retrieval', 'README.md',
                        'markdown', 'documentation', 'section', 6, 'allowed',
                        '[]', '{}', 'source:bm25-retriever',
                        'source-version:bm25-retriever:v1', 'README.md',
                        'local_directory', true, 'invited_users', 'public',
                        'allowed', 'MIT', 'redacted', 'v1'
                    ),
                    (
                        'chunk:bm25-retriever:blocked',
                        'PRIVATE.md:1-5@v1',
                        'artifact:bm25-retriever:readme',
                        'Sanitized ParadeDB BM25 retrieval documentation.',
                        'sha256:chunk-bm25-blocked', 'Retrieval',
                        'retrieval.bm25', 'bm25 retrieval', 'PRIVATE.md',
                        'markdown', 'documentation', 'section', 6,
                        'prohibited', '[]', '{}', 'source:bm25-retriever',
                        'source-version:bm25-retriever:v1', 'PRIVATE.md',
                        'local_directory', true, 'invited_users', 'public',
                        'allowed', 'MIT', 'redacted', 'v1'
                    )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO citations (
                    id, citation_key, source_url, chunk_id,
                    sanitized_content_hash, corpus_eligibility_label,
                    source_id, source_version_id, source_type, version_label,
                    source_allowlisted, visibility_label, sensitivity_class,
                    license_policy_status, license_id, redaction_status
                )
                VALUES
                    (
                        'citation:bm25-retriever:expected',
                        'citation:bm25-retriever:expected',
                        'https://example.invalid/expected',
                        'chunk:bm25-retriever:expected', 'sha256:citation-expected',
                        'allowed', 'source:bm25-retriever',
                        'source-version:bm25-retriever:v1', 'local_directory',
                        'v1', true, 'invited_users', 'public', 'allowed', 'MIT',
                        'redacted'
                    ),
                    (
                        'citation:bm25-retriever:blocked',
                        'citation:bm25-retriever:blocked',
                        'https://example.invalid/blocked',
                        'chunk:bm25-retriever:blocked', 'sha256:citation-blocked',
                        'prohibited', 'source:bm25-retriever',
                        'source-version:bm25-retriever:v1', 'local_directory',
                        'v1', true, 'invited_users', 'public', 'allowed', 'MIT',
                        'redacted'
                    )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO chunk_versions (
                    id, chunk_id, source_version_id, version_label, is_current
                )
                VALUES
                    (
                        'chunk-version:bm25-retriever:expected',
                        'chunk:bm25-retriever:expected',
                        'source-version:bm25-retriever:v1',
                        'v1',
                        true
                    ),
                    (
                        'chunk-version:bm25-retriever:blocked',
                        'chunk:bm25-retriever:blocked',
                        'source-version:bm25-retriever:v1',
                        'v1',
                        true
                    )
                """
            )
        )
