# 6.2: Weaviate Runtime And Dependency Replacement

## Goal

Add a pinned local Weaviate runtime, client configuration, and task interface while keeping the PostgreSQL stack available only for the temporary migration window.

## Prerequisites

- Step 6.1 is complete.
- The current Docker Compose PostgreSQL service remains healthy for export and shadow comparison.
- The project uses `mise` and `uv` as the documented interfaces.

## Files To Create Or Modify

- `docker-compose.yaml`
- `pyproject.toml`
- `uv.lock`
- `.env.example`
- `config/weaviate.yaml`
- `src/idp_brain/settings.py`
- `src/idp_brain/store/weaviate.py`
- `mise.toml`
- CI service configuration
- runtime smoke tests

## Implementation Instructions

1. Add the official Python Weaviate client through `uv` and pin it in `uv.lock`.
2. Add a pinned Weaviate container to Docker Compose with:
   - persistent local volume.
   - readiness and liveness checks.
   - HTTP and gRPC ports bound to localhost.
   - explicit authentication settings.
   - no floating `latest` tag.
3. Keep PostgreSQL in a migration-only Compose profile. Normal post-cutover startup must not start it.
4. Add settings for:
   - HTTP and gRPC endpoints.
   - API key or OIDC credentials when configured.
   - TLS verification.
   - connection and query timeouts.
   - consistency level.
   - active collection generation.
   - vectorizer and reranker provider headers.
5. Keep provider secrets in environment or secret configuration. Never store them in Weaviate objects or checked-in configuration.
6. Add an application-owned connection factory that:
   - opens and closes clients deterministically.
   - performs readiness checks.
   - exposes no domain-specific retrieval behavior.
   - is safe for CLI, MCP, workers, and tests.
7. Add `mise` tasks:
   - `weaviate:up`.
   - `weaviate:down`.
   - `weaviate:check`.
   - `weaviate:bootstrap`.
   - `weaviate:reset` for disposable local data only.
8. Keep existing `db:*` tasks during the migration window but mark them deprecated and migration-only.
9. Add a deterministic CI profile:
   - no external model API keys.
   - vectorization disabled for fixture collections or a pinned local vectorizer.
   - deterministic fixture vectors supplied by tests when vectorization is disabled.
10. Do not add LangChain, a second vector database abstraction, or a permanent generic storage interface only to support both backends.
11. Add startup diagnostics that report Weaviate version, readiness, configured collection generation, and enabled vectorizer modules without logging credentials.

## Tests And Checks

- `docker compose config`
- Start Weaviate and wait for readiness.
- Connect through the Python client and read server metadata.
- Verify HTTP and gRPC ports are localhost-only in the local profile.
- Verify tests run without external provider credentials.
- Verify PostgreSQL starts only when the migration profile is selected.
- `mise run ci`

## Acceptance Criteria

- A pinned Weaviate instance starts through Docker Compose.
- The Python client connects through repository-owned settings.
- CI has a deterministic no-paid-service profile.
- PostgreSQL is no longer part of the default runtime.
- The runtime adapter contains connection lifecycle only, not search logic.

## Suggested Commit Message

`feat: add weaviate runtime`
