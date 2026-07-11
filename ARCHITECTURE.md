# idp-brain Architecture

## Purpose

`idp-brain` is a single-repository RAG ingestion and retrieval pipeline for building source-backed expertise about technical tools.

The system must work with configurable tools and projects: Kubernetes platform components, CLIs, SDKs, operators, APIs, frameworks, documentation sites, and internal repositories. Tool-specific knowledge belongs in configuration and indexed evidence, not in core application logic.

The first product is not a WebApp and not a model fine-tuning project. It is a reliable pipeline that receives sources, extracts and sanitizes evidence, stores it in Weaviate, and returns citation-backed context for an LLM or human user.

## Architecture Decision

Weaviate is the only persistent knowledge and retrieval store after Phase 6.

The project intentionally removes PostgreSQL, ParadeDB `pg_search`, pgvector, SQLAlchemy, Alembic, and application-owned BM25/vector fusion from the target architecture. Existing implementation effort does not influence this decision. The priority is lower long-term maintenance through one purpose-built retrieval platform with built-in object storage, vector indexing, BM25F, hybrid search, metadata filtering, and optional model-provider integrations.

Weaviate owns:

- persistent knowledge objects and their retrieval metadata
- inverted indexes and BM25F lexical ranking
- vector storage and vector indexes
- hybrid BM25F/vector candidate fusion
- metadata pre-filtering
- collection schema and index configuration
- optional integrated vectorizer and reranker calls
- backup and restore of the persistent knowledge store

The application owns:

- source acquisition
- extraction and structure-aware chunking
- redaction before persistence
- deterministic object identifiers
- provenance and citation construction
- corpus eligibility policy
- version and source authority rules
- evidence bundle assembly
- evaluation and release gates
- retrieval diagnostics that are not provided by Weaviate

## Core Principles

- **Generic core**: the pipeline does not hardcode behavior for Crossplane, Flux, Kubernetes, or another specific project.
- **Configurable sources**: repositories, versions, source priorities, extraction profiles, and refresh rules are configuration.
- **Source-backed answers**: every important statement returned to a caller traces back to indexed evidence.
- **Freshness over memory**: current source code, generated schemas, tests, examples, and release artifacts outrank stale model knowledge.
- **Redaction before persistence**: raw secrets, disallowed PII, and unsanitized chunks never enter Weaviate, embeddings, logs, evaluation data, rerankers, or LLM context.
- **One persistent store**: Weaviate stores the knowledge objects, vectors, indexes, and retrieval metadata. The application does not maintain a second canonical database.
- **Hybrid retrieval first**: lexical and semantic retrieval are one configured Weaviate hybrid query, not two application-owned pipelines.
- **Thin application adapters**: the application translates domain models to Weaviate objects and Weaviate results to evidence bundles; it does not implement a database or search engine.
- **Separate docs and code profiles**: documentation, source code, schemas, generated artifacts, and memory may use different named vectors, tokenization, vectorizers, and query profiles.
- **Deterministic and replayable ingestion**: stable UUIDs, content hashes, source versions, and idempotent batches make a complete rebuild possible.
- **Evaluation before tuning**: model changes are promoted only when held-out retrieval metrics improve without safety, freshness, or citation regressions.

## Non-Goals

- No developer portal.
- No user-facing WebApp in the first milestone.
- No hardcoded platform-tool catalog.
- No direct mutation of indexed external systems.
- No generative LLM fine-tuning in the initial architecture.
- No second relational source of truth beside Weaviate.
- No application-owned BM25 implementation, ANN index, rank-fusion engine, or database migration framework after Phase 6.
- No "fat" MCP server that owns ingestion, model serving, workflow state, or observability.

## Repository Boundary

All application code, collection definitions, ingestion logic, retriever code, tests, configuration, and automation live in this repository.

External repositories and downloaded artifacts are ingestion inputs. They are cached outside source control and are never vendored into this repository.

## Tool Suite

### Version And Task Management

- `mise`: project tool versions, environment variables, and tasks.
- `uv`: Python dependencies and lockfile management.
- `docker compose`: local Weaviate and observability runtime.

Normal workflows are exposed as `mise` tasks. Contributors should not need to remember internal commands.

### Runtime Language

Python 3.14 owns:

- source receiving and refresh orchestration
- extraction and chunking
- metadata normalization
- redaction and policy classification
- Weaviate batch writes
- retrieval requests
- evidence and citation assembly
- evaluation
- CLI and MCP interfaces

Python does not own vector index implementation, BM25 scoring, hybrid result fusion, or persistent schema migrations after the Weaviate cutover.

### RAG Framework

LlamaIndex Python may be used for ingestion and retrieval primitives where it reduces code. It does not own source-trust policy, deterministic IDs, redaction, corpus eligibility, or the evidence bundle contract.

### Extraction Tools

The extractor set is configurable per source.

Documentation:

- Docling for local-first rich document conversion.
- `markdown-it-py` for Markdown structure.
- `beautifulsoup4` with `lxml` for HTML sections, anchors, tables, and code blocks.
- Apache Tika as an optional broad text and metadata service.
- Unstructured as an optional element-aware profile.

Source code and repositories:

- `git` for clone, fetch, tags, commits, ancestry, and diffs.
- GitHub Linguist for language, generated-file, and vendored-file classification.
- tree-sitter for symbol-aware source chunks.
- language-native tools where configured, beginning with Go.
- Semgrep for optional structured pattern extraction.
- Gitingest only as a bootstrap or debugging fallback.

Schemas and APIs:

- Python `json` and `tomllib`.
- PyYAML or `ruamel.yaml`.
- `jsonschema`.
- `openapi-spec-validator`.

Security and compliance:

- Gitleaks or detect-secrets for secret-like values.
- Microsoft Presidio for configured PII detection and anonymization.
- ScanCode Toolkit and OSS Review Toolkit for license and origin metadata.

## Weaviate Knowledge Store

### Deployment Model

The default local runtime is a pinned self-hosted Weaviate container in Docker Compose.

Production may use self-hosted Weaviate or Weaviate Cloud without changing the application domain model. Connection details, authentication, TLS, consistency level, and provider credentials are configuration.

The Python client uses the supported Weaviate client API. gRPC and HTTP ports are exposed only to localhost in the local profile. Anonymous access is allowed only for isolated local development when explicitly configured; production requires authentication and authorization.

### Collection Strategy

The target model favors a small number of collections and denormalized retrieval metadata. This avoids recreating a relational schema in an object database.

Required collections:

- `EvidenceChunk`: the primary searchable collection.
- `Source`: configured source and current refresh state.
- `SourceVersion`: immutable resolved source version metadata.
- `IngestionRun`: ingestion execution state and diagnostics.
- `MemoryItem`: optional promoted project or user memory.
- `EvaluationCase`: retrieval regression inputs.
- `EvaluationResult`: retrieval regression outputs.

Optional collections are introduced only when a concrete query or lifecycle requires them:

- `Claim`: normalized structured statements used for conflict detection.
- `Entity`: stable symbols, API fields, packages, or other normalized entities.
- `Change`: commits, pull requests, release notes, and changelog entries.

`EvidenceChunk` remains the direct retrieval unit even when optional structured collections exist.

### EvidenceChunk Shape

Every `EvidenceChunk` contains enough denormalized metadata to filter and cite it without a cross-collection join:

- deterministic object UUID
- stable chunk ID
- sanitized content
- content kind: documentation, code, schema, example, test, release note, change, or memory
- title or heading path
- repository or artifact URL
- source ID and source type
- source version ID
- commit SHA, tag, release, version, or checksum
- first and last containing version when proven
- artifact path or logical locator
- language
- package, namespace, and symbol path when available
- signature and parent symbol when available
- line start and line end when available
- source authority rank
- visibility label
- sensitivity class
- license ID and license policy status
- redaction status
- extractor name, version, and profile
- chunking profile and version
- sanitized content hash
- active state
- index generation
- first seen and last verified timestamps
- citation payload required to construct the public citation contract

Fields used by corpus eligibility are present on the searchable object so Weaviate filters are applied in the same request as retrieval.

### Deterministic IDs

Object UUIDs are derived from stable domain keys rather than generated randomly.

Examples:

- source: source ID
- source version: source ID plus immutable version locator
- artifact: source version plus artifact path or logical locator
- chunk: artifact identity plus stable chunk locator plus sanitized content hash or chunk revision
- memory item: memory scope plus stable memory ID

The exact namespace UUID and input format are versioned. Re-running the same ingestion creates or replaces the same logical objects instead of producing duplicates.

### References And Denormalization

Weaviate references may connect chunks to sources, source versions, entities, claims, or changes. Retrieval correctness must not depend on following references during the main hybrid query.

Retrieval-critical fields are duplicated on `EvidenceChunk`. References support navigation, maintenance, and structured fetch operations.

Relationship and lineage queries use one of these patterns, in order:

1. direct chunk metadata filters
2. deterministic fetch by object ID
3. bounded reference traversal for structured entities
4. a second filtered query using IDs returned by the structured lookup

The application does not introduce a separate graph or relational database.

### Collection Schema Lifecycle

Collection definitions are declared in repository-owned Python or configuration and applied idempotently by a schema bootstrap command.

Schema changes follow these rules:

- additive properties are preferred
- immutable index or vectorizer changes create a new versioned collection
- new collection generations are populated and evaluated before activation
- active collection names are resolved through application configuration
- rollback switches configuration to the previous validated collection generation
- destructive changes require an export or backup first

Alembic is not used for Weaviate schema management.

## Vectorization And Indexing

### Default Responsibility

Weaviate owns embedding generation when an integrated provider is configured. This removes application-owned embedding job tables, provider response persistence, vector columns, and vector index migrations.

The application sends sanitized content and approved metadata. Weaviate creates and indexes vectors according to the collection configuration.

Bring-your-own vectors remain supported for:

- deterministic CI fixtures
- offline or air-gapped environments
- experimental embedding models
- migration of existing vectors when reuse is explicitly useful

### Named Vectors

Named vectors keep different retrieval domains separate without separate databases.

Initial named vectors:

- `docs`: narrative documentation, examples, tables, and release notes
- `code`: source code, signatures, symbols, and nearby documentation
- `schema`: OpenAPI, JSON Schema, configuration fields, and generated API material
- `memory`: promoted non-authoritative memory items

A collection may omit vectors that do not apply to a specific object. Query profiles choose the target vector or configured set of vectors.

### Vector Index Policy

Use Weaviate's supported vector index configuration rather than application-owned ANN indexes.

Initial policy:

- use a flat or dynamic index for small collections and deterministic correctness tests
- use HNSW or the current recommended production index when corpus size requires ANN search
- configure compression only after recall and latency evaluation
- keep index parameters in collection configuration, not hardcoded in retrieval code
- create a new collection generation for incompatible vector index changes

### Lexical Index Policy

Weaviate BM25F is the lexical retrieval layer.

Searchable text properties include:

- sanitized content
- title and heading path
- symbol path and signature
- artifact path
- source and version labels where lexical matching is useful
- configured aliases and identifiers

Property tokenization and index flags are explicit in the collection definition. Exact identifiers use deterministic object fetches or filterable properties rather than a separate PostgreSQL index.

## Retrieval Architecture

Retrieval is hybrid and evidence-first.

### Query Profiles

`config/retrieval.yaml` defines named profiles:

- `docs_qa`: narrative documentation, examples, tables, and release notes
- `code_qa`: symbols, signatures, AST chunks, imports, paths, and supporting docs
- `api_symbol_lookup`: exact fields, endpoint paths, flags, class names, functions, methods, errors, and versions
- `release_change_search`: tags, releases, changelogs, commits, diffs, and version membership
- `conflict_search`: normalized claims and competing evidence

Each profile configures:

- target collection generation
- target named vector
- searchable lexical properties
- hybrid alpha and fusion mode
- result limits and auto-cut behavior where supported
- source authority and freshness reranking rules
- optional integrated or external reranker
- token budget

### Retrieval Stages

1. Parse query intent, query profile, version scope, and requested source hints.
2. Derive trusted corpus eligibility from server-side configuration.
3. Build Weaviate filters for source allowlist, visibility, sensitivity, license, redaction, version, active state, and index generation.
4. Resolve deterministic exact lookups when an ID, path, symbol, endpoint, field, version, or error identifier is present.
5. Run one Weaviate hybrid query for lexical and semantic retrieval with the filters attached.
6. Optionally run a structured claim, entity, change, or memory lookup when query intent requires it.
7. Apply application-owned source authority, freshness, version-lineage, and citation-completeness adjustments only when they are not expressible in the configured Weaviate query or reranker.
8. Optionally rerank sanitized candidates through the configured Weaviate integration or external reranker.
9. Assemble and return the evidence bundle.

The application does not run separate ParadeDB and pgvector queries and does not implement reciprocal rank fusion for the normal retrieval path.

### Exact Retrieval

Exact retrieval uses the simplest matching path:

- deterministic UUID fetch for known IDs
- equality filters for stable identifiers
- tokenization-aware BM25F with semantic weight disabled for textual identifiers
- hybrid search only when exact or lexical matching does not produce enough evidence

Exact hits and hybrid hits are deduplicated by deterministic chunk ID.

### Hybrid Search

Hybrid search is issued through Weaviate and combines BM25F and vector similarity inside the platform.

The profile controls semantic versus lexical weighting. The retriever requests score metadata and explanations when available and maps them into normalized diagnostics.

The retriever does not compare raw BM25 and vector scores itself.

### Reranking

Reranking receives only sanitized candidates that already passed corpus eligibility filters.

The preferred order is:

1. a Weaviate-supported reranker integration
2. a configured external reranker endpoint
3. no reranker when evaluation shows the hybrid ranking is sufficient

The application keeps only a small adapter for evidence metadata and diagnostics.

### Retrieval Diagnostics

`explain_search` reports:

- selected query profile
- collection generation and target vector
- applied filters
- hybrid alpha and fusion mode
- result rank and available score explanation
- exact-match reason when used
- source authority and freshness adjustments
- reranker result when used
- competing candidates and exclusion reasons where available

Raw secrets, disallowed source text, vectors, provider payloads, and hidden policy details are never returned.

## Claims, Conflicts, Relationships, And Lineage

Structured extractors may emit normalized claims and entities.

Claim shape:

- subject
- predicate
- normalized value
- value type
- scope
- confidence
- source authority
- evidence chunk IDs and citations

Conflict detection remains application-owned because it depends on domain-neutral comparator rules. Detected claims and conflict markers are stored in Weaviate.

A conflict exists only when claims share a subject and predicate, have overlapping scope, and contain incompatible values that cannot be explained by version, authority, or narrower scope.

Lineage is evidence, not inference. First and last containing versions remain unknown unless tags, releases, commit ancestry, checksums, or other source evidence proves them.

Relationship traversal is bounded. It uses denormalized chunk fields and optional Weaviate references; it does not require a second graph store.

## Memory Layer

Memory is optional and non-authoritative.

Memory may store:

- project preferences
- accepted and rejected architecture decisions
- retrieval feedback
- evaluation observations
- source policy decisions
- recurring corrections

Memory rules:

- writes require explicit promotion
- untrusted source text cannot write memory
- memory is sanitized before persistence
- memory has scope, visibility, sensitivity, provenance, retention, and expiry
- memory can influence query expansion or ranking
- memory cannot override higher-authority source evidence
- expired memory is excluded by Weaviate filters

## Pipeline Architecture

The pipeline has ten stages.

1. **Receive**
   - load source, extractor, corpus, model, and retrieval configuration
   - resolve requested refs and refresh policy
   - create an `IngestionRun` object

2. **Fetch**
   - clone or update repositories
   - download documentation, release artifacts, and schemas
   - record immutable source version metadata

3. **Discover**
   - classify files and artifacts
   - apply generated, vendored, and include/exclude rules
   - record auditable discovery decisions

4. **Extract**
   - extract text, structure, symbols, facts, claims, examples, and citations
   - preserve source provenance for every candidate chunk

5. **Redact, Classify, And Check Policy**
   - detect secrets, credentials, configured PII, and sensitive patterns
   - redact before chunking, persistence, vectorization, logging, or evaluation
   - assign visibility, sensitivity, license, and source eligibility metadata

6. **Normalize**
   - convert extractor output to Pydantic domain models
   - assign deterministic IDs and normalized metadata
   - attach version, authority, parser, and content-hash information

7. **Chunk**
   - use structural boundaries for code and documentation
   - keep paths, symbols, signatures, headings, and parent context
   - make chunk locators stable across incremental refreshes

8. **Store And Index**
   - batch upsert `Source`, `SourceVersion`, `EvidenceChunk`, and optional structured objects
   - let Weaviate vectorize and index sanitized content
   - mark removed chunks inactive or delete them according to retention policy
   - record the active collection generation

9. **Retrieve**
   - derive trusted filters
   - fetch exact identifiers when possible
   - run Weaviate hybrid search
   - run optional structured lookups and reranking
   - assemble evidence bundles

10. **Evaluate And Operate**
   - compare lexical-only, vector-only, and hybrid profiles through Weaviate
   - measure retrieval quality and latency
   - observe application and Weaviate health
   - back up, restore, and rebuild collection generations

## Ingestion And Consistency

Weaviate is not treated as a relational transaction engine. The pipeline provides consistency through deterministic, idempotent operations.

Rules:

- each ingestion run has a stable run ID and explicit state
- object writes use deterministic UUIDs
- batch failures are recorded and retried by object ID
- a source version is activated only after all required objects are written and validated
- chunks carry active state and collection generation
- removed chunks are tombstoned or deleted only after the replacement generation is valid
- retrieval filters out inactive objects and incomplete generations
- a complete rebuild from source configuration is always supported

Cross-object atomicity is not assumed. Activation flags and collection generations provide the cutover boundary.

## Evidence Bundle Contract

The retriever returns evidence bundles, not raw untrusted context.

Each evidence bundle contains:

- query and normalized intent
- selected query profile
- selected chunk IDs and sanitized excerpts
- citations
- source authority and freshness metadata
- conflict markers
- corpus eligibility result
- redaction status
- token budget estimate
- retrieval diagnostics safe for the caller

Each citation contains:

- source ID
- source URL
- commit, tag, version, or checksum
- path or logical locator
- line range when available
- source type
- sanitized content hash
- redaction status
- visibility label

## Security Model

Security applies before persistence and before retrieval reaches a reranker or LLM.

- Raw secrets are never intentionally stored in Weaviate.
- PII detection runs before vectorization for configured source profiles.
- License policy is attached before chunks become retrievable.
- Source allowlists and eligibility filters are server-owned.
- Caller hints may narrow but never expand trusted source scope.
- Documentation, examples, comments, and issue text are untrusted data.
- Prompt-like text from sources is never executed as instruction.
- Logs, traces, metrics, and profiles do not contain raw queries, chunks, vectors, secrets, credentials, provider payloads, or unbounded identifiers.
- Weaviate authentication, authorization, TLS, network policy, and backups are required outside isolated local development.

## Configuration Model

Required files:

- `config/sources.yaml`: source catalog
- `config/extractors.yaml`: extraction profiles
- `config/models.yaml`: Weaviate vectorizer, reranker, and optional generator providers
- `config/weaviate.yaml`: connection, authentication, consistency, collection generations, and index configuration
- `config/retrieval.yaml`: query profiles and result limits
- `config/evaluation.yaml`: regression cases and thresholds
- `config/security.yaml`: redaction and prompt-injection handling
- `config/corpus.yaml`: source, visibility, sensitivity, and license eligibility defaults
- `config/memory.yaml`: memory scopes, retention, and promotion

Provider API keys are environment or secret configuration and are never written into collection objects.

## Local Runtime

`docker-compose.yaml` runs Weaviate as the persistent local service.

Required service:

- `weaviate`

Optional services:

- local vectorizer modules required by the selected development profile
- Grafana Alloy
- Prometheus
- Tempo
- Loki
- Pyroscope
- Grafana

The local Weaviate volume is disposable. A schema bootstrap plus source ingestion must recreate the complete state.

Local startup is healthy when:

- the readiness endpoint succeeds
- required collections and properties exist
- a fixture object can be inserted and fetched
- a filtered BM25 query succeeds
- a filtered vector query succeeds
- a filtered hybrid query succeeds
- a deterministic exact lookup succeeds

## Mise Tasks

Required tasks after Phase 6:

```text
mise run install
mise run up
mise run down
mise run weaviate:bootstrap
mise run weaviate:reset
mise run weaviate:backup
mise run weaviate:restore-smoke-test
mise run ingest
mise run retrieve -- <query>
mise run eval
mise run lint
mise run test
mise run ci
```

Temporary compatibility tasks used only during Phase 6:

```text
mise run migration:export-postgres
mise run migration:import-weaviate
mise run migration:shadow-eval
mise run migration:cutover-check
```

The compatibility tasks are removed when the ParadeDB/PostgreSQL implementation is deleted.

## Operations And Observability

Application telemetry is vendor-neutral and uses OpenTelemetry.

Required spans:

- request receipt
- corpus eligibility derivation
- query profile selection
- deterministic exact lookup
- Weaviate hybrid retrieval
- Weaviate structured lookup
- reranking
- evidence packaging
- MCP `search` and `fetch`
- optional model call

Required metrics:

- ingestion runs, object writes, batch failures, tombstones, and redactions
- Weaviate request latency and errors by bounded operation type
- exact, hybrid, structured, reranker, and total retrieval latency
- candidate counts before and after reranking
- collection object counts, shard health, memory, storage, backup, restore, and replication metrics exposed by Weaviate
- recall, MRR, nDCG, hit rate, context precision, context recall, and abstention metrics

Weaviate Prometheus-compatible metrics are scraped by Grafana Alloy or Prometheus. The project does not run the OpenTelemetry Collector PostgreSQL receiver or `postgres_exporter` after Phase 6.

Application client spans use manual spans around repository-owned Weaviate adapters plus supported HTTP or gRPC instrumentation. They must not capture request bodies, object content, vectors, API keys, or full filters.

Backups use Weaviate's supported backup API and a configured backend. Local development uses the filesystem backup backend and restore smoke tests. Production backup retention, encryption, replication, and recovery objectives are deployment policy.

## CI And Evaluation

CI remains deterministic and independent from paid external services.

The CI Weaviate profile either:

- imports deterministic fixture vectors with vectorization disabled, or
- runs a pinned local vectorizer service when its runtime cost is acceptable

CI must not require provider API keys.

Required evaluation categories:

- exact identifier lookup
- source-code lookup
- schema and API lookup
- documentation lookup
- release and version lookup
- change-to-version lookup
- version diff retrieval
- source conflict retrieval
- stale source detection
- source, license, sensitivity, and version filters
- token budget limits
- BM25-only, vector-only, and hybrid comparisons through Weaviate
- secret and PII redaction
- citation completeness

Required metrics:

- Recall@k
- MRR
- nDCG@10
- hit rate
- p50 and p95 latency by retrieval stage
- abstention correctness

Thresholds in `config/evaluation.yaml` must exist before a regression becomes release-blocking.

## Phase Plan

### Phase 1: Skeleton And Local Runtime

Build the original Python project, task runner, local database runtime, migration baseline, and CI scaffold.

### Phase 2: Configuration And Core Data Model

Define source, policy, redaction, licensing, indexing, and domain models.

### Phase 3: Generic Ingestion And Sanitized Storage

Implement source acquisition, extraction, redaction-before-persistence, structure-aware chunking, incremental updates, and tombstones.

### Phase 4: Embeddings, ParadeDB, pgvector, And Retrieval

Complete the original retrieval implementation so its behavior and evaluation fixtures provide a measurable migration baseline.

### Phase 5: CLI, MCP, Evaluation, And CI

Expose retrieval through CLI and read-only MCP tools and establish deterministic evaluation and thresholds.

### Phase 6: Migrate From ParadeDB To Weaviate

- record the final architecture decision and migration guardrails
- add the Weaviate runtime and client configuration
- define versioned Weaviate collections and deterministic IDs
- migrate sanitized evidence, citations, source versions, claims, relationships, memory, and evaluation metadata
- move vectorization, BM25F, vector indexes, filtering, and hybrid fusion to Weaviate
- replace SQL retrieval adapters with Weaviate adapters
- run shadow retrieval and compare against the established evaluation baseline
- cut over CLI and MCP interfaces
- validate backup, restore, rebuild, and rollback
- remove PostgreSQL, ParadeDB, pgvector, SQLAlchemy, Alembic, psycopg, and obsolete migrations

### Phase 7: Day-2 Operations And OpenTelemetry

- run the local observability backend stack
- emit application metrics, logs, and traces through OpenTelemetry
- scrape Weaviate metrics
- add Weaviate backup and restore tests
- correlate traces and continuous profiles
- validate the complete stack with Python 3.14 free-threaded

## Migration Completion Criteria

The ParadeDB-to-Weaviate migration is complete when:

- Weaviate is the only required persistent service
- all active sanitized evidence is rebuildable in Weaviate from configured sources
- CLI and MCP use no PostgreSQL or ParadeDB path
- exact, lexical, semantic, hybrid, filtered, and citation fetch behavior passes the evaluation gates
- source eligibility is enforced inside every Weaviate retrieval request
- deterministic IDs make re-ingestion idempotent
- backups restore into an empty Weaviate instance
- a previous collection generation can be reactivated for rollback
- no runtime dependency on SQLAlchemy, Alembic, psycopg, pgvector, or ParadeDB remains
- documentation, Compose, settings, tasks, tests, and telemetry contain no stale PostgreSQL retrieval assumptions
