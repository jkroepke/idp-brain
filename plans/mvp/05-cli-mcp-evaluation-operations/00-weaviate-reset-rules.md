# 5.0: Normative Weaviate Reset Rules

## Status

This file is normative for every implementation step starting with Step 5.2.

It overrides requirements implied by:

- the existing PostgreSQL, ParadeDB, pgvector, SQLAlchemy, retrieval, reranking, evidence-bundle, and MCP code
- the already implemented Phase 4 behavior
- older plan files or tests that describe the former application-owned retrieval architecture

An implementation agent must treat the existing backend code as deletion input, not as an API compatibility contract.

## Capabilities That Are Not Required

The following capabilities are explicitly **not part of the MVP target architecture** and must not be ported to Weaviate.

### Derive Trusted Corpus Eligibility At Query Time

Do not implement application-side caller eligibility derivation for the initial trusted single-user or single-team service.

Instead:

- classify and sanitize evidence during ingestion
- write evidence only to the collection or tenant whose callers may access it
- use Weaviate authentication, RBAC, collections, tenants, and credentials as the access boundary

Reconsider query-time eligibility only after a concrete multi-caller requirement cannot be represented safely by those Weaviate boundaries.

### Apply Mandatory Source, Visibility, Sensitivity, License, Version, Active-State, And Index-Generation Filters

Do not port the canonical SQL scopes or inject hidden filters into every query.

For the MVP:

- source, visibility, sensitivity, and license eligibility determine which authorized collection or tenant receives an object during ingestion
- current and historical evidence may use separate collections or explicitly selected collections when history is introduced
- active-state and index-generation query filters are replaced by versioned blue-green collections
- only a validated collection generation is exposed to CLI and MCP credentials

Explicit user-selected Weaviate filters may be added later for search refinement. They are not a hidden application security layer.

### Perform Deterministic Exact Lookups

Do not port the application-owned exact retriever or make exact lookup a completion requirement.

The MVP uses Weaviate hybrid search. A narrow UUID or equality-property lookup may be introduced later only when measured usage requires citation reuse, identifier lookup, or lower context cost.

### Apply Application-Owned Authority And Freshness Adjustments

Do not port custom authority tie-breaking, freshness weighting, RRF tie signals, or a second reranking stage.

For the MVP:

- expose current validated evidence through collection design
- compare BM25-only, vector-only, and hybrid Weaviate profiles through evaluation
- use a Weaviate-supported reranker or ranking feature only after evaluation demonstrates a need

Source authority and timestamps may remain returned metadata for diagnostics. They do not require application-side score adjustment.

### Produce Separate Stable Citation Objects

Do not port the SQL-backed citation repository, citation joins, or a separate application citation-object assembly pipeline.

Each `EvidenceChunk` stores stable citation properties directly, including source URL, immutable source version, locator, line range, content hash, and redaction status. CLI and MCP return those properties with the matching evidence object.

Stable citation metadata is required. A separate citation entity, DTO graph, or fetch pipeline is not.

### Assemble An Evidence Bundle

Do not port `EvidenceAssembler`, the SQL-backed evidence fetcher, token-budget packaging, conflict-marker packaging, or the large `EvidenceBundle` response contract.

The result of a Weaviate query is already the MVP evidence response: ranked sanitized chunks with citation properties and bounded score metadata.

Add a formal evidence bundle only after a real non-LLM downstream consumer requires a stable aggregate API contract.

### Provide Custom `fetch` And `explain_search` MCP Tools

Do not implement custom MCP `fetch`, `explain_search`, or `list_sources` tools.

Use Weaviate's built-in hybrid MCP tool as the default agent interface.

- `fetch` is deferred until returning full query results proves too expensive or citation IDs are reused frequently.
- search explanation is an operator and evaluation concern; a bounded CLI diagnostic may be added later.
- neither capability justifies an application-owned MCP server in the MVP.

## Required MVP Retrieval Surface

The complete required retrieval surface is intentionally small:

1. one validated versioned `EvidenceChunk` collection
2. direct Weaviate hybrid search from the CLI and evaluation runner
3. Weaviate's built-in read-only MCP server
4. sanitized content and citation properties returned on every result
5. behavioral evaluation of BM25-only, vector-only, and hybrid profiles

## Mandatory Deletion Guidance

When replacing the backend, delete rather than adapt code that exists only to provide the removed capabilities. This includes, where present:

- `src/idp_brain/retrieval/corpus_filters.py`
- the application exact, BM25, and vector retrievers
- reciprocal-rank fusion and related score models
- application authority and freshness ranking
- `src/idp_brain/retrieval/evidence.py` and its evidence-bundle DTOs and fetchers
- the default application reranker registry and mock reranker
- custom MCP server and tool modules
- tests asserting canonical SQL scopes, exact-retriever behavior, RRF arithmetic, evidence-bundle snapshots, or custom MCP tools

Do not preserve these modules behind compatibility interfaces. Do not create replacement protocols merely to retain their shapes.

## Acceptance Criteria

- implementation work does not port any removed capability merely because matching code already exists
- the default retrieval path is one direct Weaviate query
- access boundaries use Weaviate-native authorization and collection or tenant design
- citations are returned as properties of evidence objects
- no custom evidence bundle, exact retriever, authority/freshness adjustment, `fetch`, or `explain_search` MCP tool is required for MVP completion
