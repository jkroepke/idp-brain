# 4.1: Embedding Provider Interface

## Goal
Create the application-owned embedding provider interface and registry, including a deterministic local/mock provider for CI and explicit gating for any external embedding provider.

## Prerequisites
- `ARCHITECTURE.md` has been read and remains the source of truth.
- Phase 2 has introduced typed loading for `config/models.yaml`.
- Phase 3 has introduced sanitized chunks with stable sanitized content hashes.
- No external model API is required for local development or CI.

## Files To Create Or Modify
- `config/models.yaml`
- `src/idp_brain/embeddings/__init__.py`
- `src/idp_brain/embeddings/providers.py`
- `src/idp_brain/embeddings/mock.py`
- `src/idp_brain/config/models.py`
- `tests/embeddings/test_embedding_provider_interface.py`
- `tests/embeddings/test_mock_embedding_provider.py`

## Implementation Instructions
1. Define an application-owned `EmbeddingProvider` protocol in `src/idp_brain/embeddings/providers.py`; do not expose LlamaIndex, OpenAI, Jina, or any vendor object as the core interface.
2. Define typed inputs and outputs:
   - `EmbeddingInput(chunk_id: UUID, sanitized_text: str, sanitized_content_hash: str, metadata: Mapping[str, str])`
   - `EmbeddingVector(values: list[float], dimensions: int, provider_id: str, model_id: str)`
   - `EmbeddingProvider.embed(inputs: Sequence[EmbeddingInput]) -> list[EmbeddingVector]`
3. Make `EmbeddingInput.sanitized_text` the only text field accepted by the interface. Do not accept raw extractor output, raw chunk text, raw file content, or arbitrary debug payloads.
4. Add `EmbeddingProfile` config models for profile ID, provider ID, model name, dimensions, batch size, timeout, external-provider flag, and environment variables required for credentials.
5. Add the MVP profiles in `config/models.yaml`:
   - `docs_default`
   - `docs_quality`
   - `code_default`
   - `memory_default`
   Each profile must have a deterministic `mock` option for CI. External providers such as OpenAI, Jina, or local model-serving endpoints are allowed only as disabled profiles until explicitly enabled.
6. Implement `DeterministicMockEmbeddingProvider` in `src/idp_brain/embeddings/mock.py`. It must produce stable vectors from `sanitized_content_hash`, profile ID, model ID, and configured dimension, without network access and without process-randomized hashing.
7. Normalize mock vectors to a deterministic numeric range and assert the returned vector length equals the configured dimension.
8. Add a provider registry that resolves a provider by profile ID and rejects external providers unless both the profile is marked enabled and `IDP_BRAIN_ALLOW_EXTERNAL_MODELS=true` is set.
9. Never log request text, response vectors, credentials, or provider payloads. Log only provider ID, model ID, dimensions, batch size, count, elapsed time, and sanitized content hashes when needed for diagnostics.
10. If an optional external provider adapter is stubbed in this step, make it fail closed with a clear configuration error when credentials or explicit external-provider permission are absent.
11. Keep embedding fine-tuning out of scope; this step creates the baseline provider boundary only.

## Tests And Checks
- `uv run pytest tests/embeddings/test_embedding_provider_interface.py`
- `uv run pytest tests/embeddings/test_mock_embedding_provider.py`
- `uv run pytest tests/config/test_models_config.py`
- Test that identical sanitized content hashes produce identical vectors across runs.
- Test that changing the model ID, profile ID, dimension, or sanitized content hash changes the mock output deterministically.
- Test that external providers are rejected when `IDP_BRAIN_ALLOW_EXTERNAL_MODELS` is unset or false.
- Test that no provider log record contains `sanitized_text`, raw text, API keys, or response vectors.

## Acceptance Criteria
- The retriever and embedding jobs depend on the application-owned provider interface, not vendor SDK types.
- CI can generate embeddings deterministically with no network access and no secrets.
- External embedding providers are opt-in, disabled by default, and gated by configuration plus environment.
- The interface cannot be called with raw unsanitized chunks.
- Provider diagnostics are useful without leaking raw content, vectors, or credentials.

## Suggested Commit Message
`feat: add embedding provider interface`
