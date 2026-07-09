"""Application-owned embedding provider boundary."""

from idp_brain.embeddings.jobs import (
    EmbeddingJobExecutionError,
    EmbeddingJobPlan,
    EmbeddingJobRunResult,
    create_embedding_jobs_for_index_version,
    run_embedding_jobs_once,
)
from idp_brain.embeddings.mock import DeterministicMockEmbeddingProvider
from idp_brain.embeddings.providers import (
    EmbeddingInput,
    EmbeddingProvider,
    EmbeddingProviderConfigError,
    EmbeddingProviderRegistry,
    EmbeddingVector,
)
from idp_brain.embeddings.storage import EmbeddingVectorRepository

__all__ = [
    "DeterministicMockEmbeddingProvider",
    "EmbeddingJobExecutionError",
    "EmbeddingJobPlan",
    "EmbeddingJobRunResult",
    "EmbeddingInput",
    "EmbeddingProvider",
    "EmbeddingProviderConfigError",
    "EmbeddingProviderRegistry",
    "EmbeddingVector",
    "EmbeddingVectorRepository",
    "create_embedding_jobs_for_index_version",
    "run_embedding_jobs_once",
]
