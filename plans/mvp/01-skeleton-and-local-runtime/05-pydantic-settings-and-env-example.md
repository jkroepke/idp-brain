# 1.5: Pydantic Settings And Env Example

## Goal
Add typed application settings and a safe environment example so later database, ingestion, retrieval, evaluation, and MCP components use one validated configuration entry point.

## Prerequisites
- Phase 1.1 through Phase 1.4 are complete.
- Read `ARCHITECTURE.md`, especially `Configuration Model`, `Embeddings, Reranking, And Model Serving`, and `Security Model`.
- Local PostgreSQL can be started with `mise run up`.

## Files To Create Or Modify
- `pyproject.toml`
- `uv.lock`
- `.env.example`
- `src/idp_brain/settings.py`
- `tests/test_settings.py`

## Implementation Instructions
1. Add `pydantic-settings` as a runtime dependency.
2. Create `Settings` in `src/idp_brain/settings.py` using `BaseSettings`.
3. Configure settings to read environment variables with the `IDP_BRAIN_` prefix and to ignore unknown variables.
4. Include these initial fields with safe defaults:
   - `database_url`: compatible with local compose, for example `postgresql+psycopg://idp_brain:idp_brain@localhost:55432/idp_brain`
   - `log_level`: default `INFO`
   - `config_dir`: default `config`
   - `cache_dir`: default `.idp-brain-cache`
   - `embedding_provider`: default `mock`
   - `external_model_calls_enabled`: default `false`
5. Make `external_model_calls_enabled=false` the default for local development and CI so tests cannot call external model providers unless explicitly opted in later.
6. Add `.env.example` with all `IDP_BRAIN_` keys required by this step and safe development values only. Do not include real secrets, tokens, API keys, or private URLs.
7. Add a reusable loader function such as `load_settings()` that returns `Settings`.
8. Add tests that verify defaults, environment overrides, `.env.example` key coverage, and that external model calls default to disabled.
9. Do not read source catalog YAML files, fetch source data, connect to model providers, connect to PostgreSQL, or create ingestion caches in this step.

## Tests And Checks
- `uv sync`
- `uv run pytest tests/test_settings.py`
- `mise run lint`
- `mise run test`
- Passing condition: settings load with defaults, environment overrides work, `.env.example` remains secret-free, and lint/type checks pass.

## Acceptance Criteria
- The app has one typed settings entry point.
- `.env.example` documents safe local values without secrets.
- External model calls are disabled by default.
- No raw source data is loaded, persisted, embedded, logged, returned, or sent to a model provider.

## Suggested Commit Message
`feat: add typed application settings`
