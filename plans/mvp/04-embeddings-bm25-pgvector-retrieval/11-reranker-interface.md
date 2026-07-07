# 4.11: Reranker Interface

## Goal
Create a separate reranker interface with a deterministic local/mock reranker for CI and explicit gating for external reranker providers.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Step 4.8 defines reranker profile IDs and whether reranking is enabled per query profile.
- Step 4.9 filters all candidates before reranker payload construction.
- Step 4.10 produces fused candidates with path diagnostics.
- Evidence packaging has not yet exposed final context to CLI or MCP.

## Files To Create Or Modify
- `src/idp_brain/reranking/__init__.py`
- `src/idp_brain/reranking/providers.py`
- `src/idp_brain/reranking/mock.py`
- `src/idp_brain/retrieval/service.py`
- `src/idp_brain/config/models.py`
- `config/models.yaml`
- `tests/reranking/test_reranker_interface.py`
- `tests/reranking/test_mock_reranker.py`
- `tests/retrieval/test_reranking_integration.py`

## Implementation Instructions
1. Define an application-owned `Reranker` protocol. It must accept the sanitized query string, fused candidate IDs, sanitized excerpts or sanitized summary text, sanitized metadata, and profile settings.
2. Do not pass raw unsanitized chunks, raw extractor output, raw local cache content, ineligible metadata, or unfiltered candidates to the reranker.
3. Add typed `RerankerProfile` config for provider ID, model name, enabled flag, external-provider flag, candidate limit, timeout, max text length, and required credential environment variables.
4. Implement `DeterministicMockReranker` for CI. It should produce stable ordering from lexical overlap, existing fused rank, authority rank, freshness, and chunk ID, without network access or process-randomized hashing.
5. Add disabled optional profiles for local/private BGE reranker v2 m3, Jina Reranker v2 multilingual, and Cohere Rerank. External or remote providers must require explicit profile enablement and `IDP_BRAIN_ALLOW_EXTERNAL_MODELS=true`.
6. Truncate reranker input by configured token or character budget after sanitization, and record truncation counts without logging text.
7. Preserve fusion diagnostics after reranking so `explain_search` can show both fused rank and reranked rank later.
8. Fail closed if a query profile requires reranking but no enabled reranker profile is available.
9. Keep reranking as a service call boundary. Do not implement reranking inside SQL or as a database concern.
10. Add timeout handling and sanitized error diagnostics. External provider failures should either fall back to fused ordering when the profile allows fallback or fail the request clearly.

## Tests And Checks
- `uv run pytest tests/reranking/test_reranker_interface.py`
- `uv run pytest tests/reranking/test_mock_reranker.py`
- `uv run pytest tests/retrieval/test_reranking_integration.py`
- Test deterministic mock reranking across repeated runs.
- Test that unfiltered or unsanitized candidates are rejected before reranker calls.
- Test that external rerankers are disabled unless explicitly gated by config and environment.
- Test fallback behavior when reranking is optional and fail-closed behavior when reranking is required.
- Test that logs and diagnostics do not include full candidate text, secrets, credentials, or raw provider responses.

## Acceptance Criteria
- Reranking is behind an application-owned interface and separate from database retrieval.
- CI uses a deterministic local/mock reranker with no external services.
- External reranker providers are opt-in, disabled by default, and fail closed without explicit permission.
- Reranker inputs contain sanitized, corpus-filtered content only.
- Fusion and reranking diagnostics remain available for later evidence bundles and explain output.

## Suggested Commit Message
`feat: add reranker interface`
