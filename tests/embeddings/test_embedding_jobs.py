from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from idp_brain.config.models import EmbeddingProfileConfig
from idp_brain.embeddings import (
    DeterministicMockEmbeddingProvider,
    EmbeddingInput,
    EmbeddingVector,
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


class FailingProvider:
    provider_id = "mock"
    model_id = "failing-mock"
    dimensions = 3

    def embed(self, inputs: Sequence[EmbeddingInput]) -> list[EmbeddingVector]:
        raise RuntimeError("provider failed with password=hunter2 api_key=sk-secret")


def test_embedding_jobs_are_created_only_for_current_sanitized_allowed_chunks() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_base_graph(session)
            _add_chunk(session, "chunk:allowed", "safe [REDACTED:SECRET:1]")
            _add_chunk(
                session,
                "chunk:blocked-redaction",
                "unsafe text",
                redaction_status="blocked",
            )
            _add_chunk(
                session,
                "chunk:denied-license",
                "safe denied text",
                license_policy_status="denied",
                license_id="Proprietary",
            )
            session.commit()

            plan = create_embedding_jobs_for_index_version(
                session,
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test",
            )
            jobs = session.scalars(select(EmbeddingJob)).all()

            assert plan.created_jobs == 1
            assert plan.skipped_chunks == 2
            assert [job.chunk_id for job in jobs] == ["chunk:allowed"]
            assert jobs[0].sanitized_content_hash == "sha256:chunk:allowed"
    finally:
        engine.dispose()


def test_embedding_planning_honors_index_version_source_scope() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_base_graph(session)
            _add_source_graph(session, source_id="source:other")
            _add_chunk(session, "chunk:allowed", "safe [REDACTED:SECRET:1]")
            _add_chunk(
                session,
                "chunk:out-of-scope",
                "safe but outside this index",
                source_id="source:other",
                source_version_id="source-version:other",
                artifact_id="artifact:other",
            )
            session.commit()

            plan = create_embedding_jobs_for_index_version(
                session,
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test",
            )
            jobs = session.scalars(select(EmbeddingJob)).all()

            assert plan.created_jobs == 1
            assert [job.chunk_id for job in jobs] == ["chunk:allowed"]
    finally:
        engine.dispose()


def test_worker_embeds_sanitized_text_and_persists_active_vector() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_base_graph(session)
            _add_chunk(session, "chunk:allowed", "safe [REDACTED:SECRET:1]")
            create_embedding_jobs_for_index_version(
                session,
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test",
            )

            result = run_embedding_jobs_once(
                session,
                provider=DeterministicMockEmbeddingProvider(_profile()),
                batch_size=10,
            )
            embedding = session.scalar(select(Embedding))
            job = session.scalar(select(EmbeddingJob))

            assert result.claimed_jobs == 1
            assert result.succeeded_jobs == 1
            assert embedding is not None
            assert embedding.is_active is True
            assert embedding.dimensions == 3
            assert embedding.sanitized_content_hash == "sha256:chunk:allowed"
            assert job is not None
            assert job.status == "succeeded"
            assert job.provider_request_hash is not None
            assert "safe [REDACTED" not in job.provider_request_hash
    finally:
        engine.dispose()


def test_failed_terminal_job_is_reset_on_replan_without_duplicate_insert() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_base_graph(session)
            _add_chunk(session, "chunk:allowed", "safe [REDACTED:SECRET:1]")
            create_embedding_jobs_for_index_version(
                session,
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test",
            )
            run_embedding_jobs_once(
                session,
                provider=FailingProvider(),
                batch_size=10,
                max_attempts=1,
            )
            failed_job = session.scalar(select(EmbeddingJob))
            assert failed_job is not None
            assert failed_job.status == "failed"
            assert failed_job.sanitized_error_message is not None

            plan = create_embedding_jobs_for_index_version(
                session,
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test",
            )
            jobs = session.scalars(select(EmbeddingJob)).all()

            assert plan.created_jobs == 1
            assert len(jobs) == 1
            assert jobs[0].id == failed_job.id
            assert jobs[0].status == "pending"
            assert jobs[0].attempt_count == 0
            assert jobs[0].sanitized_error_code is None
            assert jobs[0].sanitized_error_message is None
    finally:
        engine.dispose()


def test_provider_failures_store_sanitized_terminal_diagnostics() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            _add_base_graph(session)
            _add_chunk(session, "chunk:allowed", "safe [REDACTED:SECRET:1]")
            create_embedding_jobs_for_index_version(
                session,
                embedding_model_id="embedding-model:mock",
                index_version_id="index-version:test",
            )

            result = run_embedding_jobs_once(
                session,
                provider=FailingProvider(),
                batch_size=10,
                max_attempts=1,
            )
            job = session.scalar(select(EmbeddingJob))

            assert result.failed_jobs == 1
            assert job is not None
            assert job.status == "failed"
            assert job.sanitized_error_code == "RuntimeError"
            assert job.sanitized_error_message is not None
            assert "hunter2" not in job.sanitized_error_message
            assert "sk-secret" not in job.sanitized_error_message
            assert "[redacted]" in job.sanitized_error_message
    finally:
        engine.dispose()


def _profile() -> EmbeddingProfileConfig:
    return EmbeddingProfileConfig(
        profile_id="docs_default",
        provider_id="mock",
        model_name="deterministic-docs-default-v1",
        dimensions=3,
        deterministic=True,
    )


def _add_base_graph(session: Session) -> None:
    _add_source_graph(session, source_id="source:test")
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


def _add_source_graph(session: Session, *, source_id: str) -> None:
    source_version_id = source_id.replace("source:", "source-version:")
    artifact_id = source_id.replace("source:", "artifact:")
    ingestion_run_id = source_id.replace("source:", "ingestion:")
    session.add(
        Source(
            id=source_id,
            config_key=source_id,
            name=source_id,
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
            id=source_version_id,
            source_id=source_id,
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
            id=ingestion_run_id,
            source_id=source_id,
            source_version_id=source_version_id,
            status="completed",
            stats={},
        )
    )
    session.add(
        Artifact(
            id=artifact_id,
            artifact_key=artifact_id,
            artifact_type="document",
            title="Fixture",
            sanitized_content_hash="sha256:artifact",
            source_id=source_id,
            source_version_id=source_version_id,
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


def _add_chunk(
    session: Session,
    chunk_id: str,
    sanitized_text: str,
    *,
    redaction_status: str = "redacted",
    license_policy_status: str = "allowed",
    license_id: str | None = "MIT",
    source_id: str = "source:test",
    source_version_id: str = "source-version:test",
    artifact_id: str = "artifact:test",
) -> Chunk:
    chunk = Chunk(
        id=chunk_id,
        chunk_key=chunk_id,
        artifact_id=artifact_id,
        sanitized_text=sanitized_text,
        sanitized_content_hash=f"sha256:{chunk_id}",
        artifact_path="fixture.md",
        source_id=source_id,
        source_version_id=source_version_id,
        source_type="local_directory",
        source_allowlisted=True,
        visibility_label="invited_users",
        sensitivity_class="public",
        license_policy_status=license_policy_status,
        license_id=license_id,
        redaction_status=redaction_status,
        corpus_eligibility_label="eligible",
    )
    session.add(chunk)
    session.flush()
    session.add(
        ChunkVersion(
            id=f"chunk-version:{chunk_id}",
            chunk_id=chunk_id,
            source_version_id=source_version_id,
            version_label="v1",
            checksum=chunk.sanitized_content_hash,
            is_current=True,
        )
    )
    session.flush()
    return chunk
