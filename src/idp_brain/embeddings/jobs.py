"""Local sanitized embedding job planning and execution."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from idp_brain.embeddings.providers import EmbeddingInput, EmbeddingProvider
from idp_brain.embeddings.storage import EmbeddingVectorRepository
from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.models import (
    Chunk,
    ChunkVersion,
    Embedding,
    EmbeddingJob,
    EmbeddingModel,
    IndexVersion,
)
from idp_brain.models.base import utc_now

EMBEDDABLE_REDACTION_STATUSES = frozenset({"redacted", "not_required"})
EMBEDDABLE_LICENSE_POLICY_STATUSES = frozenset({"allowed"})
TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
RETRYABLE_JOB_STATUSES = frozenset({"pending", "retrying"})
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 30


@dataclass(frozen=True)
class EmbeddingJobPlan:
    """Summary of embedding jobs created for an index version."""

    created_jobs: int
    skipped_chunks: int
    deactivated_vectors: int


@dataclass(frozen=True)
class EmbeddingJobRunResult:
    """Summary of one bounded local embedding worker pass."""

    claimed_jobs: int
    succeeded_jobs: int
    failed_jobs: int
    retrying_jobs: int
    cancelled_jobs: int
    deactivated_vectors: int


def create_embedding_jobs_for_index_version(
    session: Session,
    *,
    embedding_model_id: str,
    index_version_id: str,
    limit: int | None = None,
) -> EmbeddingJobPlan:
    """Create jobs for active, sanitized chunks missing current embeddings."""

    source_ids = _source_ids_for_index_version(session, index_version_id)
    query = (
        select(Chunk)
        .join(ChunkVersion, ChunkVersion.chunk_id == Chunk.id)
        .where(
            ChunkVersion.is_current.is_(True),
            Chunk.source_version_id.is_not(None),
        )
        .order_by(Chunk.id)
    )
    if source_ids is not None:
        query = query.where(Chunk.source_id.in_(source_ids))
    if limit is not None:
        query = query.limit(limit)

    vector_repository = EmbeddingVectorRepository(session)
    created_jobs = 0
    skipped_chunks = 0
    deactivated_vectors = _deactivate_unembeddable_active_vectors(
        session,
        vector_repository=vector_repository,
        embedding_model_id=embedding_model_id,
        index_version_id=index_version_id,
        source_ids=source_ids,
    )
    for chunk in session.scalars(query):
        if not _chunk_is_embeddable(chunk) or not _chunk_has_current_version(
            session, chunk.id
        ):
            deactivated_vectors += vector_repository.deactivate_stale_vectors(
                chunk_id=chunk.id,
                embedding_model_id=embedding_model_id,
                index_version_id=index_version_id,
            )
            skipped_chunks += 1
            continue
        if _has_active_embedding(
            session,
            chunk_id=chunk.id,
            embedding_model_id=embedding_model_id,
            index_version_id=index_version_id,
            sanitized_content_hash=chunk.sanitized_content_hash,
        ):
            continue
        if _has_open_job(
            session,
            chunk_id=chunk.id,
            embedding_model_id=embedding_model_id,
            index_version_id=index_version_id,
            sanitized_content_hash=chunk.sanitized_content_hash,
        ):
            continue
        if _reset_failed_terminal_job(
            session,
            chunk_id=chunk.id,
            embedding_model_id=embedding_model_id,
            index_version_id=index_version_id,
            sanitized_content_hash=chunk.sanitized_content_hash,
        ):
            created_jobs += 1
            continue
        job = EmbeddingJob(
            id=_stable_job_id(
                chunk_id=chunk.id,
                embedding_model_id=embedding_model_id,
                index_version_id=index_version_id,
                sanitized_content_hash=chunk.sanitized_content_hash,
            ),
            chunk_id=chunk.id,
            embedding_model_id=embedding_model_id,
            index_version_id=index_version_id,
            sanitized_input_hash=chunk.sanitized_content_hash,
            sanitized_content_hash=chunk.sanitized_content_hash,
            status="pending",
            attempt_count=0,
            provider_response_metadata={},
        )
        session.add(job)
        created_jobs += 1
    session.flush()
    return EmbeddingJobPlan(
        created_jobs=created_jobs,
        skipped_chunks=skipped_chunks,
        deactivated_vectors=deactivated_vectors,
    )


def run_embedding_jobs_once(
    session: Session,
    *,
    provider: EmbeddingProvider,
    batch_size: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> EmbeddingJobRunResult:
    """Claim and execute a bounded batch of local embedding jobs."""

    now = utc_now()
    jobs = list(
        session.scalars(
            select(EmbeddingJob)
            .where(
                EmbeddingJob.status.in_(RETRYABLE_JOB_STATUSES),
                (
                    (EmbeddingJob.next_retry_at.is_(None))
                    | (EmbeddingJob.next_retry_at <= now)
                ),
            )
            .order_by(EmbeddingJob.created_at, EmbeddingJob.chunk_id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    vector_repository = EmbeddingVectorRepository(session)
    result = _MutableJobRunResult(claimed_jobs=len(jobs))
    for job in jobs:
        job.status = "running"
        job.attempt_count += 1
        job.updated_at = utc_now()
        session.flush()

        chunk = session.get(Chunk, job.chunk_id)
        model = session.get(EmbeddingModel, job.embedding_model_id)
        if (
            chunk is None
            or model is None
            or not _chunk_is_embeddable(chunk)
            or not _chunk_has_current_version(session, job.chunk_id)
        ):
            result.deactivated_vectors += vector_repository.deactivate_stale_vectors(
                chunk_id=job.chunk_id,
                embedding_model_id=job.embedding_model_id,
                index_version_id=job.index_version_id,
            )
            _cancel_job(job, "chunk is no longer embeddable")
            result.cancelled_jobs += 1
            continue
        if chunk.sanitized_content_hash != job.sanitized_content_hash:
            result.deactivated_vectors += vector_repository.deactivate_stale_vectors(
                chunk_id=job.chunk_id,
                embedding_model_id=job.embedding_model_id,
                index_version_id=job.index_version_id,
            )
            _cancel_job(job, "chunk content hash changed before embedding")
            result.cancelled_jobs += 1
            continue

        input_item = _embedding_input_from_chunk(chunk)
        try:
            vector = provider.embed([input_item])[0]
            if vector.dimensions != model.dimensions:
                raise EmbeddingJobExecutionError(
                    "embedding provider returned unexpected vector dimensions"
                )
            if len(vector.values) != model.dimensions:
                raise EmbeddingJobExecutionError(
                    "embedding provider returned malformed vector length"
                )
        except Exception as exc:
            _record_job_error(job, exc, max_attempts=max_attempts)
            if job.status == "retrying":
                result.retrying_jobs += 1
            else:
                result.failed_jobs += 1
            continue

        vector_repository.upsert_vector(
            chunk_id=chunk.id,
            embedding_model_id=job.embedding_model_id,
            index_version_id=job.index_version_id,
            sanitized_content_hash=chunk.sanitized_content_hash,
            vector=vector.values,
            dimensions=vector.dimensions,
            distance_metric=model.distance_metric,
        )
        job.status = "succeeded"
        job.sanitized_error_code = None
        job.sanitized_error_message = None
        job.next_retry_at = None
        job.provider_request_hash = _provider_request_hash(input_item)
        job.provider_response_metadata = {
            "provider_id": vector.provider_id,
            "model_id": vector.model_id,
            "dimensions": vector.dimensions,
        }
        job.updated_at = utc_now()
        result.succeeded_jobs += 1
    session.flush()
    return result.freeze()


class EmbeddingJobExecutionError(RuntimeError):
    """Raised for safe local embedding worker validation failures."""


@dataclass
class _MutableJobRunResult:
    claimed_jobs: int
    succeeded_jobs: int = 0
    failed_jobs: int = 0
    retrying_jobs: int = 0
    cancelled_jobs: int = 0
    deactivated_vectors: int = 0

    def freeze(self) -> EmbeddingJobRunResult:
        return EmbeddingJobRunResult(
            claimed_jobs=self.claimed_jobs,
            succeeded_jobs=self.succeeded_jobs,
            failed_jobs=self.failed_jobs,
            retrying_jobs=self.retrying_jobs,
            cancelled_jobs=self.cancelled_jobs,
            deactivated_vectors=self.deactivated_vectors,
        )


def _chunk_is_embeddable(chunk: Chunk) -> bool:
    return (
        chunk.source_allowlisted
        and chunk.source_version_id is not None
        and bool(chunk.sanitized_text)
        and chunk.redaction_status in EMBEDDABLE_REDACTION_STATUSES
        and chunk.license_policy_status in EMBEDDABLE_LICENSE_POLICY_STATUSES
    )


def _chunk_has_current_version(session: Session, chunk_id: str) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    ChunkVersion.chunk_id == chunk_id,
                    ChunkVersion.is_current.is_(True),
                    ChunkVersion.tombstoned_at.is_(None),
                )
            )
        )
    )


def _deactivate_unembeddable_active_vectors(
    session: Session,
    *,
    vector_repository: EmbeddingVectorRepository,
    embedding_model_id: str,
    index_version_id: str,
    source_ids: frozenset[str] | None,
) -> int:
    deactivated = 0
    active_chunk_ids = list(
        session.scalars(
            select(Embedding.chunk_id)
            .where(
                Embedding.embedding_model_id == embedding_model_id,
                Embedding.index_version_id == index_version_id,
                Embedding.is_active.is_(True),
            )
            .distinct()
        )
    )
    for chunk_id in active_chunk_ids:
        chunk = session.get(Chunk, chunk_id)
        if (
            chunk is None
            or (source_ids is not None and chunk.source_id not in source_ids)
            or not _chunk_is_embeddable(chunk)
            or not _chunk_has_current_version(session, chunk_id)
        ):
            deactivated += vector_repository.deactivate_stale_vectors(
                chunk_id=chunk_id,
                embedding_model_id=embedding_model_id,
                index_version_id=index_version_id,
            )
    return deactivated


def _source_ids_for_index_version(
    session: Session,
    index_version_id: str,
) -> frozenset[str] | None:
    index_version = session.get(IndexVersion, index_version_id)
    if index_version is None:
        raise ValueError(f"unknown index version {index_version_id!r}")

    raw_source_ids = index_version.source_scope.get("source_ids")
    if raw_source_ids is None:
        return None
    source_ids = frozenset(
        source_id for source_id in raw_source_ids if isinstance(source_id, str)
    )
    return source_ids or frozenset()


def _has_active_embedding(
    session: Session,
    *,
    chunk_id: str,
    embedding_model_id: str,
    index_version_id: str,
    sanitized_content_hash: str,
) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    Embedding.chunk_id == chunk_id,
                    Embedding.embedding_model_id == embedding_model_id,
                    Embedding.index_version_id == index_version_id,
                    Embedding.sanitized_content_hash == sanitized_content_hash,
                    Embedding.is_active.is_(True),
                )
            )
        )
    )


def _has_open_job(
    session: Session,
    *,
    chunk_id: str,
    embedding_model_id: str,
    index_version_id: str,
    sanitized_content_hash: str,
) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    EmbeddingJob.chunk_id == chunk_id,
                    EmbeddingJob.embedding_model_id == embedding_model_id,
                    EmbeddingJob.index_version_id == index_version_id,
                    EmbeddingJob.sanitized_content_hash == sanitized_content_hash,
                    EmbeddingJob.status.not_in(TERMINAL_JOB_STATUSES),
                )
            )
        )
    )


def _reset_failed_terminal_job(
    session: Session,
    *,
    chunk_id: str,
    embedding_model_id: str,
    index_version_id: str,
    sanitized_content_hash: str,
) -> bool:
    job = session.scalar(
        select(EmbeddingJob).where(
            EmbeddingJob.chunk_id == chunk_id,
            EmbeddingJob.embedding_model_id == embedding_model_id,
            EmbeddingJob.index_version_id == index_version_id,
            EmbeddingJob.sanitized_content_hash == sanitized_content_hash,
            EmbeddingJob.status == "failed",
        )
    )
    if job is None:
        return False
    job.status = "pending"
    job.attempt_count = 0
    job.next_retry_at = None
    job.provider_request_hash = None
    job.provider_response_metadata = {}
    job.sanitized_error_code = None
    job.sanitized_error_message = None
    job.updated_at = utc_now()
    session.flush()
    return True


def _embedding_input_from_chunk(chunk: Chunk) -> EmbeddingInput:
    metadata = {
        "source_id": chunk.source_id,
        "source_version_id": chunk.source_version_id or "",
        "artifact_id": chunk.artifact_id,
        "chunk_key": chunk.chunk_key,
        "corpus_eligibility_label": chunk.corpus_eligibility_label,
        "visibility_label": chunk.visibility_label,
        "sensitivity_class": chunk.sensitivity_class,
        "license_policy_status": chunk.license_policy_status,
        "redaction_status": chunk.redaction_status,
    }
    return EmbeddingInput(
        chunk_id=uuid5(NAMESPACE_URL, chunk.id),
        sanitized_text=chunk.sanitized_text,
        sanitized_content_hash=chunk.sanitized_content_hash,
        metadata=metadata,
    )


def _record_job_error(
    job: EmbeddingJob,
    error: BaseException,
    *,
    max_attempts: int,
) -> None:
    job.sanitized_error_code = type(error).__name__
    job.sanitized_error_message = sanitize_diagnostic_text(str(error))
    job.provider_response_metadata = {"error_type": type(error).__name__}
    job.updated_at = utc_now()
    if job.attempt_count >= max_attempts:
        job.status = "failed"
        job.next_retry_at = None
    else:
        job.status = "retrying"
        job.next_retry_at = utc_now() + timedelta(seconds=DEFAULT_RETRY_DELAY_SECONDS)


def _cancel_job(job: EmbeddingJob, message: str) -> None:
    job.status = "cancelled"
    job.next_retry_at = None
    job.sanitized_error_code = "EmbeddingJobCancelled"
    job.sanitized_error_message = sanitize_diagnostic_text(message)
    job.provider_response_metadata = {}
    job.updated_at = utc_now()


def _provider_request_hash(input_item: EmbeddingInput) -> str:
    payload = "\x1f".join(
        (
            str(input_item.chunk_id),
            input_item.sanitized_content_hash,
            *[f"{key}={value}" for key, value in sorted(input_item.metadata.items())],
        )
    )
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _stable_job_id(
    *,
    chunk_id: str,
    embedding_model_id: str,
    index_version_id: str,
    sanitized_content_hash: str,
) -> str:
    payload = "\x1f".join(
        (chunk_id, embedding_model_id, index_version_id, sanitized_content_hash)
    )
    return f"embedding-job:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
