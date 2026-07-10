from __future__ import annotations

from idp_brain.config.models import EmbeddingProfileConfig
from idp_brain.embeddings import DeterministicMockEmbeddingProvider
from idp_brain.retrieval.models import (
    RetrievalFilters,
    RetrievalQuery,
    VectorRetrievalProfile,
)
from idp_brain.retrieval.vector import _query_embedding_input


def test_query_embedding_input_uses_sanitized_query_and_safe_metadata_only() -> None:
    profile = VectorRetrievalProfile(
        profile_id="docs_vector",
        embedding_profile_id="docs_default",
        embedding_model_id="embedding-model:mock",
        index_version_id="index-version:test",
    )
    input_item = _query_embedding_input(
        RetrievalQuery(query_text="find password=hunter2 in raw source"),
        RetrievalFilters(source_ids=("source:secret",), version_labels=("v1",)),
        profile,
    )

    assert input_item.sanitized_text == "find [redacted] in raw source"
    assert input_item.sanitized_content_hash.startswith("sha256:")
    assert input_item.metadata == {
        "profile_id": "docs_vector",
        "embedding_profile_id": "docs_default",
        "source_filter_count": "1",
        "version_filter_count": "1",
    }
    assert "source:secret" not in repr(input_item.metadata)
    assert "hunter2" not in input_item.sanitized_text


def test_query_embedding_is_deterministic_with_mock_provider() -> None:
    profile = EmbeddingProfileConfig(
        profile_id="docs_default",
        provider_id="mock",
        model_name="deterministic-docs-default-v1",
        dimensions=8,
        deterministic=True,
    )
    vector_profile = VectorRetrievalProfile(
        profile_id="docs_vector",
        embedding_profile_id="docs_default",
        embedding_model_id="embedding-model:mock",
        index_version_id="index-version:test",
    )
    input_item = _query_embedding_input(
        RetrievalQuery(query_text="vector retrieval"),
        RetrievalFilters(),
        vector_profile,
    )
    provider = DeterministicMockEmbeddingProvider(profile)

    first = provider.embed([input_item])[0]
    second = provider.embed([input_item])[0]

    assert first.values == second.values
    assert first.dimensions == 8
