from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from idp_brain.config.models import EmbeddingProfileConfig
from idp_brain.embeddings import (
    DeterministicMockEmbeddingProvider,
    create_embedding_jobs_for_index_version,
    run_embedding_jobs_once,
)
from idp_brain.models import (
    Artifact,
    Base,
    Chunk,
    ChunkVersion,
    Embedding,
    EmbeddingJob,
    EmbeddingModel,
    IndexVersion,
    IngestionRun,
    Source,
    SourceVersion,
)


def test_changed_sanitized_hash_creates_new_active_vector_and_stales_old_one() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_base_graph(session)
            chunk = _add_chunk(session, "chunk:changed", "safe first")
            _embed_pending(session)

            first = session.scalar(select(Embedding))
            assert first is not None
            assert first.is_active is True

            chunk.sanitized_text = "safe second [REDACTED:SECRET:1]"
            chunk.sanitized_content_hash = "sha256:chunk:changed:v2"
            version = session.scalar(
                select(ChunkVersion).where(ChunkVersion.chunk_id == chunk.id)
            )
            assert version is not None
            version.checksum = chunk.sanitized_content_hash
            create_embedding_jobs_for_index_version(
                session,
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test",
            )
            _embed_pending(session)

            embeddings = session.scalars(
                select(Embedding).order_by(Embedding.created_at, Embedding.id)
            ).all()
            assert len(embeddings) == 2
            assert [embedding.is_active for embedding in embeddings].count(True) == 1
            active = next(embedding for embedding in embeddings if embedding.is_active)
            stale = next(
                embedding for embedding in embeddings if not embedding.is_active
            )
            assert active.sanitized_content_hash == "sha256:chunk:changed:v2"
            assert stale.sanitized_content_hash == "sha256:chunk:changed"
    finally:
        engine.dispose()


def test_tombstoned_chunks_do_not_retain_active_embeddings() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            chunk = _add_base_graph_and_embedding(session)
            version = session.scalar(
                select(ChunkVersion).where(ChunkVersion.chunk_id == chunk.id)
            )
            assert version is not None
            chunk.source_version_id = None
            version.is_current = False
            version.tombstone_reason = "removed"

            plan = create_embedding_jobs_for_index_version(
                session,
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test",
            )
            active_embeddings = session.scalars(
                select(Embedding).where(Embedding.is_active.is_(True))
            ).all()

            assert plan.deactivated_vectors == 1
            assert active_embeddings == []
    finally:
        engine.dispose()


def _add_base_graph_and_embedding(session: Session) -> Chunk:
    _add_base_graph(session)
    _add_chunk(session, "chunk:tombstone", "safe [REDACTED:SECRET:1]")
    _embed_pending(session)
    session.expire_all()
    persisted = session.get(Chunk, "chunk:tombstone")
    assert persisted is not None
    return persisted


def _add_base_graph(session: Session) -> None:
    session.add(
        Source(
            id="source:test",
            config_key="test-source",
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
    session.add(
        IngestionRun(
            id="ingestion:test",
            source_id="source:test",
            source_version_id="source-version:test",
            status="completed",
            stats={},
        )
    )
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
            external_calls_allowed=False,
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
            status="building",
            built_from_ingestion_run_id="ingestion:test",
            failure_metadata={},
        )
    )
    session.flush()


def _add_chunk(session: Session, chunk_id: str, sanitized_text: str) -> Chunk:
    chunk = Chunk(
        id=chunk_id,
        chunk_key=chunk_id,
        artifact_id="artifact:test",
        sanitized_text=sanitized_text,
        sanitized_content_hash=f"sha256:{chunk_id}",
        artifact_path="fixture.md",
        source_id="source:test",
        source_version_id="source-version:test",
        source_type="local_directory",
        source_allowlisted=True,
        visibility_label="invited_users",
        sensitivity_class="public",
        license_policy_status="allowed",
        license_id="MIT",
        redaction_status="redacted",
        corpus_eligibility_label="eligible",
    )
    session.add(chunk)
    session.flush()
    session.add(
        ChunkVersion(
            id=f"chunk-version:{chunk_id}",
            chunk_id=chunk_id,
            source_version_id="source-version:test",
            version_label="v1",
            checksum=chunk.sanitized_content_hash,
            is_current=True,
        )
    )
    session.flush()
    return chunk


def _embed_pending(session: Session) -> None:
    create_embedding_jobs_for_index_version(
        session,
        embedding_model_id="embedding-model:mock",
        index_version_id="index-version:test",
    )
    result = run_embedding_jobs_once(
        session,
        provider=DeterministicMockEmbeddingProvider(
            EmbeddingProfileConfig(
                profile_id="docs_default",
                provider_id="mock",
                model_name="deterministic-docs-default-v1",
                dimensions=3,
                deterministic=True,
            )
        ),
        batch_size=10,
    )
    assert result.failed_jobs == 0
    session.execute(
        EmbeddingJob.__table__.delete().where(EmbeddingJob.status == "succeeded")
    )
