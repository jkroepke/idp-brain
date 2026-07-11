# 5.8: Remove The Legacy Stack

## Goal

Delete the obsolete persistence, retrieval, evidence-bundle, reranker, and MCP implementation after the Weaviate vertical path and evaluation pass.

Step 5.0 is normative. Existing modules, public classes, tests, and response DTOs do not create compatibility requirements.

## Capabilities To Delete, Not Port

The implementation agent must explicitly remove or stop using code that provides these former requirements:

- query-time trusted corpus eligibility derivation
- mandatory application-side source, visibility, sensitivity, license, version, active-state, and index-generation filters
- application-owned deterministic exact lookup retrieval
- application-owned authority and freshness score adjustments
- separate stable citation-object assembly
- evidence-bundle assembly and token-budget packaging
- custom MCP `fetch`, `explain_search`, and `list_sources` tools

These capabilities are not MVP acceptance criteria. Their Weaviate-native replacements are defined in Step 5.0.

Do not retain them behind compatibility adapters, protocols, feature flags, deprecated modules, or alternate code paths. Do not rewrite SQL implementations as equivalent Weaviate wrappers.

## Remove

- PostgreSQL and ParadeDB Compose services
- PostgreSQL volumes, health checks, and environment settings
- SQLAlchemy, Alembic, psycopg, pgvector, and ParadeDB dependencies
- `migrations/`
- ORM models used only for persistence
- SQL repository implementations
- embedding jobs and stored vectors
- exact, BM25, and vector SQL retrievers
- canonical corpus-filter SQL scopes and query-time eligibility derivation
- reciprocal rank fusion
- authority and freshness tie-breaking or post-query score adjustment
- default application reranker registry and mock
- SQL-backed citation repositories and citation joins
- `EvidenceAssembler`, SQL-backed evidence fetchers, evidence-bundle DTOs, snapshots, conflict packaging, and token-budget packaging
- custom MCP server and custom `search`, `fetch`, `explain_search`, and `list_sources` tools
- database backup, reset, migrate, and check tasks
- PostgreSQL integration tests
- tests that validate removed implementation details
- PostgreSQL-specific OpenTelemetry instrumentation and metrics receiver configuration

Likely deletion targets include, where present:

- `src/idp_brain/retrieval/corpus_filters.py`
- `src/idp_brain/retrieval/exact.py`
- application BM25 and vector retriever modules
- `src/idp_brain/retrieval/fusion.py`
- `src/idp_brain/retrieval/evidence.py`
- application retrieval orchestration that exists only to combine those paths
- the default `src/idp_brain/reranking/` implementation
- application-owned MCP modules

Review imports before deleting files, but preserve only behavior required by Steps 5.0 through 5.7. The existence of an import is not evidence that the old abstraction must survive.

## Preserve

- reusable source and extractor configuration
- fetchers, discovery, extraction, redaction, and chunking
- deterministic identity helpers used for Weaviate object UUIDs
- sanitized CLI behavior
- citation and provenance properties written directly on each `EvidenceChunk`
- the thin direct Weaviate retrieval adapter used by CLI and evaluation
- Weaviate integration and behavioral evaluation tests

## Replacement Assertions

After deletion, the repository must demonstrate:

- access boundaries use Weaviate RBAC plus authorized collections or tenants, not hidden application filters
- versioned blue-green collections replace active-state and index-generation query filters
- one direct Weaviate hybrid query replaces exact/BM25/vector orchestration and RRF
- Weaviate ranking is used without application authority or freshness adjustment
- citation metadata is returned directly on evidence objects without a separate citation entity pipeline
- ranked Weaviate objects replace the evidence-bundle contract
- Weaviate's built-in MCP server replaces custom MCP tools
- exact fetch and search explanation remain deferred, optional future features

## Checks

- dependency and import searches find no runtime PostgreSQL stack
- searches for removed capability names identify no active implementation path
- no custom MCP server remains
- no application `fetch` or `explain_search` MCP tool remains
- no RRF, exact retriever, corpus-filter query scope, authority/freshness post-processing, or evidence-bundle assembly remains
- no compatibility interface preserves the old retrieval architecture
- Docker Compose contains Weaviate as the only persistent application service
- `uv lock` is regenerated
- `mise run ci`

## Acceptance Criteria

The repository contains one active persistence and retrieval architecture, not a deprecated compatibility layer. An implementation agent cannot infer from the historical codebase that the removed capabilities remain required.
