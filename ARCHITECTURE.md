# idp-brain Architecture

## Purpose

`idp-brain` builds a local-first, source-backed knowledge index for technical documentation, source code, schemas, releases, and related artifacts.

The application acquires sources, extracts structure, redacts unsafe content, creates stable evidence chunks, and writes those chunks to Weaviate. Weaviate stores and indexes the evidence and exposes it to agents through its built-in read-only MCP server.

The first milestone is not a Web application, a general workflow engine, or an application-owned search platform.

## Architecture Decision

Weaviate is the only persistent knowledge and retrieval service in the target architecture.

The existing PostgreSQL, ParadeDB, pgvector, SQLAlchemy, Alembic, embedding-job, BM25, vector-retrieval, reciprocal-rank-fusion, reranker, evidence-bundle, and custom MCP implementation is treated as disposable pre-MVP code. There is no production dataset that must be preserved. The searchable state is rebuilt from configured source material.

This change is an **architecture reset**, not a production data migration:

- no PostgreSQL export format
- no permanent compatibility layer
- no dual writes
- no object-by-object backfill requirement
- no rollback to PostgreSQL
- no requirement to preserve existing embeddings or scores
- no score parity between the old and new retrieval engines

A short-lived vertical slice may run beside the old stack only long enough to validate Weaviate before the old code is deleted.

## Explicitly Retired Requirements

The following former requirements are **not required for the MVP** and must not be inferred from the existing codebase, Phase 4 tests, public classes, DTOs, or older plans:

- derive trusted corpus eligibility at query time
- apply mandatory application-side source, visibility, sensitivity, license, version, active-state, or index-generation filters to every request
- perform application-owned deterministic exact retrieval
- apply application-owned authority or freshness score adjustments
- produce separate stable citation objects through a citation repository or assembly pipeline
- assemble an application-owned evidence bundle
- provide custom MCP `fetch`, `explain_search`, or `list_sources` tools

The replacement rules are:

- classify, sanitize, and route evidence during ingestion; use Weaviate RBAC, collections, tenants, and credentials for caller boundaries
- use authorized collections or tenants instead of hidden mandatory application filters
- use versioned blue-green collections instead of active-state and index-generation query filters
- use one direct Weaviate hybrid query instead of exact/BM25/vector orchestration and RRF
- use Weaviate ranking without application authority or freshness adjustment
- store stable citation metadata directly on each `EvidenceChunk`; a separate citation entity or DTO graph is unnecessary
- return ranked sanitized Weaviate objects with citation properties instead of an evidence bundle
- use Weaviate's built-in MCP hybrid tool; defer exact fetch and search explanation until measured usage proves they are needed

These capabilities may be reconsidered only after a concrete requirement cannot be met safely or efficiently by Weaviate-native authorization, collection design, returned object properties, and direct retrieval. They are not compatibility obligations.

The normative implementation detail is defined in `plans/mvp/05-cli-mcp-evaluation-operations/00-weaviate-reset-rules.md`.

## Preserve And Replace Boundary

### Preserve

The following work remains part of the product:

- source catalog and configuration loading
- repository and artifact fetching
- discovery and generated or vendored file classification
- extractor interfaces and structure-aware extraction
- redaction before persistence
- license and source classification needed during ingestion
- structure-aware chunking
- stable source, version, artifact, and chunk identity
- sanitized diagnostics
- the `ingest` CLI surface
- reusable evaluation cases and expected evidence identifiers
- generic test fixtures that do not depend on PostgreSQL behavior

### Replace

The following implementation is removed rather than ported:

- PostgreSQL and ParadeDB runtime
- SQLAlchemy ORM models and repositories
- Alembic migrations
- psycopg and pgvector integration
- embedding job tables and vector persistence
- separate exact, BM25, and vector retrievers
- application-owned reciprocal rank fusion
- application-owned authority and freshness ranking
- application-owned reranker registry for the default path
- SQL-backed evidence-bundle assembly
- application-owned MCP transport and tools
- database-specific lifecycle and backup tasks
- tests that assert SQL, ORM, migration, RRF, or PostgreSQL implementation details

## Responsibility Split

### Application Responsibilities

Python owns:

- source acquisition
- extraction
- redaction and sanitization
- chunk construction
- deterministic UUID input material
- citation and provenance properties written on each chunk
- collection definitions and idempotent bootstrap
- Weaviate batch writes
- a thin retrieval adapter for CLI and evaluation
- evaluation and release gates
- application telemetry

The application must not recreate a database abstraction framework merely to hide Weaviate. A small `EvidenceStore` boundary is acceptable only where it makes ingestion testable.

### Weaviate Responsibilities

Weaviate owns:

- persistent evidence objects
- vectorization when an integrated vectorizer is configured
- vector storage and vector indexes
- BM25F lexical indexing
- hybrid lexical and semantic fusion
- result ranking
- optional supported reranking
- authentication and RBAC
- collection or tenant isolation
- the built-in MCP server
- backup and restore
- Prometheus-compatible service metrics

## Collection Model

The initial implementation requires one searchable collection:

- `EvidenceChunk_<generation>`

Do not recreate the former relational schema as many Weaviate collections.

An optional `IngestionRun` collection may be introduced only when persisted operational history is proven necessary. Until then, ingestion status may be returned by the current process and emitted through sanitized structured telemetry.

### EvidenceChunk Properties

Every object is self-contained for retrieval and citation:

- deterministic UUID
- stable chunk ID
- sanitized content
- content kind
- title or heading path
- source ID and source type
- repository or artifact URL
- immutable source version
- commit SHA, tag, release, version, or checksum when available
- artifact path or logical locator
- symbol path, signature, language, and parent context when available
- line start and line end when available
- extractor and chunking profile versions
- sanitized content hash
- redaction status
- citation ID or citation fields
- optional source authority metadata for diagnostics
- first-seen and last-verified timestamps where useful

Only sanitized data may be sent to Weaviate or to an integrated vectorizer.

### Collection Generations

Incompatible schema, vectorizer, tokenization, or index changes create a new collection generation.

The process is:

1. bootstrap a new versioned collection
2. rebuild it from configured sources
3. run evaluation
4. expose the validated collection
5. remove an obsolete generation later

This blue-green collection model replaces active-state and index-generation filters on every query. Rebuilding from source is the normal recovery and upgrade path.

## Security Model

The initial product is a trusted single-user or single-team local service.

Security boundaries are expressed with Weaviate authentication, RBAC, collections, tenants, and credentials. Do not depend on an application MCP proxy to inject hidden filters.

When different callers must see different evidence, use separate authorized collections or tenants, for example:

- `EvidencePublic_<generation>`
- `EvidenceInternal_<generation>`
- `EvidenceRestricted_<generation>`

Only evidence eligible for a collection is written into it. The default MCP credential is read-only and has access only to the intended collection or tenant.

If a future requirement cannot be expressed safely through Weaviate RBAC, tenants, collection design, and returned properties, an application-owned MCP facade may be reconsidered. It is not part of the MVP.

## Ingestion Architecture

The pipeline is:

1. load source configuration
2. fetch or refresh source material
3. discover eligible artifacts
4. extract text and structure
5. redact and classify
6. normalize provenance
7. create stable chunks
8. batch write sanitized `EvidenceChunk` objects to Weaviate

The current front half of the ingestion pipeline should be adapted, not rewritten. Persistence-specific repository calls are replaced with a narrow Weaviate batch writer.

Writes are idempotent through deterministic UUIDs. Failed batch objects are reported by object ID and retried safely.

## Retrieval Architecture

### Default Retrieval

Normal retrieval is one Weaviate hybrid query.

The thin Python adapter used by CLI and evaluation may configure:

- collection generation
- target named vector
- lexical properties
- `alpha`
- result limit
- returned properties
- returned score metadata

It must not:

- execute separate ParadeDB and pgvector queries
- compute reciprocal rank fusion
- compare raw lexical and vector scores
- implement a second reranking framework
- build a large application-specific evidence bundle
- add a second policy engine in front of Weaviate

Each result object already contains sanitized evidence and stable citation properties.

### Exact Lookup

A dedicated exact-fetch feature is deferred.

Known UUID or property lookup may be added later when real usage requires citation reuse or lower context costs. It must not block the initial hybrid-search path.

### Explain Search

Search explanation is an operator and evaluation concern, not an MCP requirement.

A future CLI diagnostic may expose bounded Weaviate score metadata. The MVP does not need an `explain_search` MCP tool.

## MCP Architecture

Use Weaviate's built-in MCP server:

- documentation: https://docs.weaviate.io/weaviate/configuration/mcp-server
- endpoint: `/v1/mcp`
- Streamable HTTP transport
- write access disabled
- read-only API credentials
- RBAC restricted to the intended collection or tenant
- customized tool descriptions where useful

The built-in hybrid query tool is the default agent interface.

`idp-brain` does not implement:

- an MCP stdio or HTTP server
- custom `search`, `fetch`, `explain_search`, or `list_sources` tools
- duplicate MCP authentication
- duplicate MCP lifecycle or transport observability

A custom facade is introduced only after evaluation demonstrates a concrete capability or security gap.

## CLI Architecture

The application keeps:

- `idp-brain ingest run`
- `idp-brain ingest status` where status is available
- `idp-brain retrieve query`
- `idp-brain eval run`

The retrieval CLI is a thin operator and test surface over the official Weaviate client. It returns selected evidence and citation properties without reimplementing the MCP server.

## Evaluation

Existing evaluation cases are reused where they describe user-visible retrieval behavior.

Evaluation compares Weaviate profiles such as:

- BM25-only
- vector-only
- hybrid
- different named vectors
- optional Weaviate-supported reranking

Required signals include:

- expected evidence IDs
- Recall@k
- MRR
- nDCG
- hit rate
- citation-property completeness
- redaction safety
- latency
- deterministic fixture behavior

Raw score equality with PostgreSQL, ParadeDB, pgvector, or RRF is not meaningful and is not tested.

## Local Runtime

The required local service is a pinned Weaviate container.

The local profile:

- binds client, gRPC, and MCP endpoints to localhost
- enables the built-in MCP server
- disables MCP write access
- uses a disposable data volume
- supports collection bootstrap and rebuild from sources

Optional local services include an integrated vectorizer and the observability stack.

## Required Mise Tasks

```text
mise run install
mise run up
mise run down
mise run weaviate:bootstrap
mise run weaviate:reset
mise run ingest
mise run retrieve -- <query>
mise run eval
mise run lint
mise run test
mise run ci
```

No PostgreSQL export, import, shadow-write, or cutover task is required.

## Operations And Observability

Application metrics, logs, and traces use OpenTelemetry and export through Grafana Alloy.

Tracing includes:

- manual application spans around ingestion and the thin Weaviate adapter
- `opentelemetry-instrumentation-weaviate`
- `opentelemetry-instrumentation-threading`
- `opentelemetry-instrumentation-urllib`
- supported gRPC client instrumentation used by the pinned Weaviate client

Logging and uncaught exceptions use:

- `opentelemetry-instrumentation-logging`
- `opentelemetry-instrumentation-exceptions`

Instrumented Weaviate and transport spans are children of stable application spans. Telemetry must not capture raw queries, chunks, vectors, filters, credentials, headers, URL query strings, request bodies, response bodies, or provider payloads.

Alloy or Prometheus scrapes Weaviate's Prometheus-compatible metrics. Backups use Weaviate's backup API.

## Implementation Plan

### Phases 1 Through 4

These phases describe the implemented PostgreSQL-based baseline. Their code is historical input to the reset, not a target to preserve.

### Phase 5.1

The ingest CLI is already implemented and remains the command surface to adapt.

### Phase 5.2 Through 5.9: Weaviate Architecture Reset

- prove one complete Weaviate vertical slice
- add the runtime and one versioned `EvidenceChunk` collection
- replace ingestion persistence with direct batch writes
- replace retrieval with one direct hybrid query
- enable and test the built-in read-only MCP server
- adapt evaluation to Weaviate behavior
- delete the legacy database, retrieval, evidence-bundle, reranker, and custom MCP stack
- prove the result from a clean checkout

### Phase 6: Day-2 Operations

- run the local observability stack
- export application metrics, logs, traces, and profiles
- scrape Weaviate metrics
- test Weaviate backup and restore
- validate the complete dependency graph with Python 3.14 free-threaded

## Reset Completion Criteria

The reset is complete when:

- Weaviate is the only required persistent service
- a clean checkout can rebuild all searchable state from configured sources
- ingestion writes sanitized chunks directly to Weaviate
- the retrieval CLI issues direct Weaviate queries
- the built-in read-only Weaviate MCP server returns evidence and citation properties
- evaluation passes without comparing legacy scores
- no runtime dependency on PostgreSQL, ParadeDB, pgvector, SQLAlchemy, Alembic, or psycopg remains
- application-owned query-time eligibility derivation, mandatory hidden filters, exact retrieval, authority/freshness adjustments, separate citation assembly, evidence-bundle assembly, and custom MCP tools are removed
- no migration export, dual-write, compatibility, or PostgreSQL rollback path remains
