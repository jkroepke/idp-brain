# idp-brain Architecture

## Purpose

`idp-brain` is a single-repository RAG pipeline and retriever for building source-backed expertise about technical tools.

The system must work with any configurable tool or project: Kubernetes platform tools, CLIs, SDKs, operators, APIs, frameworks, or internal repositories. Tool-specific knowledge belongs in configuration and extracted data, not in core application logic.

The first product is not a WebApp and not a generative-model fine-tuning project. It is a reliable pipeline that receives sources, extracts facts, indexes retrievable chunks, and returns evidence-backed context for an LLM or human user.

## Core Principles

- **Generic core**: the pipeline does not know about specific Crossplane functions, Flux resources, or any other tool-specific behavior.
- **Configurable sources**: all target tools, repositories, versions, source priorities, and extractor rules are defined in configuration.
- **Source-backed answers**: every important claim must trace back to indexed evidence.
- **Freshness over memory**: current source code, generated artifacts, schemas, examples, tests, and release tags outrank stale model knowledge.
- **Baseline RAG before tuning**: embedding fine-tuning is allowed only after baseline retrieval metrics exist and prove the need.
- **Local-first runtime**: PostgreSQL with pgvector and ParadeDB `pg_search` runs locally through Docker Compose.
- **Hybrid retrieval first**: BM25 lexical search and dense vector search are both first-class retrieval paths; neither is a later add-on.
- **Separate docs and code lanes**: documentation, source code, schemas, and generated artifacts use different extractor, chunking, embedding, and query profiles before converging in normalized metadata and fused retrieval.
- **Thin integration layers**: MCP exposes search and fetch tools; it does not own ingestion, model serving, workflow state, or observability.

## Non-Goals

- No developer portal.
- No user-facing WebApp in the first phase.
- No hardcoded platform-tool catalog.
- No hardcoded blueprint generator for one specific tool stack.
- No direct mutation of external systems.
- No generative LLM fine-tuning in the initial architecture.
- No embedding fine-tuning until baseline retrieval, evaluation data, and redaction are working.
- No "fat" MCP server that replaces the retrieval service, long-running workflow system, model server, or API gateway.

## Repository Boundary

All source code for the receiver, ingestion pipeline, extractors, database schema, retriever, tests, configuration, and automation lives in this repository:

```text
/home/codex/idp-brain
```

External repositories are cloned or downloaded only as ingestion inputs. They are cached outside source control and are never vendored into this repository.

## Exact Tool Suite

### Version And Task Management

- `mise`: project tool versions, environment variables, and tasks.
- `uv`: Python dependency and lockfile management.
- `docker compose`: local service runtime.

All normal workflows must be exposed as `mise` tasks. Contributors should not need to remember raw internal commands.

### Runtime Language

- Python 3.14.

Python owns:

- source receiving
- ingestion orchestration
- extraction
- chunking
- metadata normalization
- database writes
- embedding generation
- retrieval
- reranking
- citation assembly
- CLI and optional API

### RAG Framework

- LlamaIndex Python, pinned through `uv.lock` when introduced.

LlamaIndex is used for ingestion and retrieval primitives. The source-trust policy, metadata model, ranking rules, and citation contract remain application-owned.

### Document Conversion

- Docling, pinned through `uv.lock`.
- LlamaIndex Docling reader/node-parser integrations, pinned through `uv.lock`.
- Apache Tika, optional service profile for broad file text and metadata extraction.
- Unstructured, optional profile for element-aware extraction from PDFs, Office files, HTML, and rich documents.
- `markdown-it-py` for Markdown parsing when Markdown structure should be preserved directly.
- `beautifulsoup4` with `lxml` for HTML section, heading, anchor, table, and code-block extraction.

Docling is the local-first rich document receiver. Apache Tika and Unstructured are configured extraction profiles, not mandatory runtime dependencies for every installation. They are used when the corpus requires broader file-format coverage or element-level document structure. None of these tools is used for source code, generated schemas, or structured API extraction when native extractors are available.

### Repository Digesting

- Gitingest, pinned through `uv.lock`.

Gitingest is used as an optional repository digest receiver. It can produce prompt-friendly repository summaries, directory trees, token statistics, and delimited file-content dumps. It is useful for fast bootstrap indexing, unknown languages, small repositories, smoke tests, and retrieval debugging.

Gitingest is not the primary source-code extractor when structured extractors are available. It must not replace tree-sitter, language-native tooling, schema extractors, or file-level provenance in the authoritative index.

### Source Code And Repository Classification

- GitHub Linguist for language detection, vendored-file detection, generated-file detection, and repository language statistics.
- tree-sitter for syntax-tree-aware source chunking by class, function, method, interface, type, import, and docstring boundaries.
- language-native tools where configured, starting with Go:
  - `go list`
  - `go doc`
  - `go mod graph`
  - `go test -list`
- Semgrep for optional static pattern extraction when structured rules add useful facts.

Source-code chunks must preserve symbol context: repository, commit SHA, path, language, package or namespace, symbol path, signature, docstring, imports, and containing parent symbol when available. Generated and vendored files are excluded by default unless a source profile explicitly opts in.

### Retrieval Evaluation

Baseline retrieval must work before any embedding tuning is attempted.

Initial evaluation stack:

- LlamaIndex ingestion and node abstractions.
- LlamaIndex retrieval evaluation utilities.
- pytest for regression fixtures and release gates.
- Ragas for optional answer-quality and context-quality metrics.
- DeepEval for optional reference-free answer-quality checks.

Synthetic query-context pairs may be generated from indexed chunks to evaluate retrieval. They are not source-of-truth records and must not be ranked as authoritative evidence.

Optional Phase 6 embedding tuning dependencies are not part of the MVP toolchain:

- LlamaIndex embedding fine-tuning utilities.
- Sentence Transformers.
- PyTorch.

### Embeddings, Reranking, And Model Serving

The MVP requires one configured embedding provider, but the architecture keeps documentation and code profiles separate from the start.

Initial embedding profiles:

- `docs_default`: OpenAI `text-embedding-3-small` when external API use is allowed; local alternatives are BAAI `bge-m3` or Jina `jina-embeddings-v3`.
- `docs_quality`: OpenAI `text-embedding-3-large`, Jina `jina-embeddings-v3`, or BAAI `bge-m3` when quality is more important than storage and latency.
- `code_default`: use the docs profile only for bootstrap and only if evaluation passes; promote a dedicated code model such as Jina `jina-code-embeddings-1.5b` or Nomic `nomic-embed-code` when code-heavy evaluation requires it.
- `memory_default`: same provider family as `docs_default`, but indexed separately and never treated as authoritative source evidence.

Initial reranker profiles:

- BAAI BGE reranker v2 m3 for local or private multilingual reranking.
- Jina Reranker v2 multilingual for local or API-based multilingual reranking.
- Cohere Rerank only when an external API is explicitly allowed.

Model serving is outside MCP. Self-hosted embedding, reranking, or generation endpoints use vLLM, BentoML, or KServe. Provider routing, budgets, fallbacks, and model-call logging use LiteLLM when multiple model providers are configured.

### Database

- PostgreSQL 18 with pgvector and ParadeDB `pg_search`.
- Local Docker image: approved PostgreSQL-compatible image that includes pgvector and `pg_search`, or a repository-owned custom image that installs both.
- Required extensions:
  - `vector`
  - `pg_search`
  - `pg_trgm`

Do not assume the stock `pgvector/pgvector:pg18` image contains ParadeDB `pg_search`. The repository must provide or reference a Docker build and CI check that verifies required extensions with `CREATE EXTENSION`.

Minimum extension smoke test:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

Database libraries:

- SQLAlchemy 2
- Alembic
- psycopg 3
- pgvector Python integration
- ParadeDB SQLAlchemy helpers where useful, with plain SQL allowed for BM25-specific queries

Relational tables remain the canonical storage model. BM25 and vector indexes are retrieval indexes over sanitized relational records.

### Hybrid Retrieval Store

The first production retrieval store is **ParadeDB `pg_search` + pgvector inside PostgreSQL**.

Responsibilities:

- `pg_search` owns BM25 lexical search over sanitized chunk text, symbol names, headings, paths, source metadata, and other filterable fields that need lexical ranking or pushdown.
- pgvector owns dense retrieval over embedding columns, with separate logical indexes for documentation, source code, memory, and future model versions when needed.
- PostgreSQL B-tree, partial, and trigram indexes support exact identifiers, corpus eligibility filters, and fallback fuzzy matching.
- The retrieval service owns fusion, reranking, corpus eligibility enforcement, provenance shaping, and diagnostics.

Initial pgvector policy:

- Use exact vector search for small or highly selective filtered subsets.
- Use HNSW as the default ANN index for broad dense retrieval.
- Use IVFFlat only when faster bulk index builds or lower memory use are more important than the HNSW recall/latency profile.
- Enable and test iterative scans for filtered ANN queries.
- Tune `hnsw.ef_search` and candidate counts through `config/retrieval.yaml`, not hardcoded constants.

Initial BM25 policy:

- Use ParadeDB BM25 indexes on `chunks` and selected metadata fields, with a stable chunk ID as the key field.
- Include metadata fields in BM25 indexes when filter pushdown or ranked metadata search is expected.
- Treat BM25 score and vector distance as different scoring domains. Merge candidate sets with rank fusion or calibrated weighted fusion before reranking.
- Keep PostgreSQL native FTS as a fallback or diagnostic tool only if it proves useful; it is not the primary lexical layer.

Initial migration pattern:

```sql
CREATE INDEX chunks_bm25_idx
ON chunks
USING bm25 (
    id,
    sanitized_text,
    heading_path,
    symbol_path,
    signature_text,
    artifact_path,
    source_type,
    language,
    version_label,
    visibility_label,
    sensitivity_class
)
WITH (key_field = 'id');

CREATE INDEX embeddings_hnsw_cosine_idx
ON embeddings
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX chunks_exact_symbol_idx
ON chunks (source_id, version_label, language, symbol_path)
WHERE symbol_path IS NOT NULL;
```

Initial query shape:

```sql
-- BM25 candidate generation through pg_search.
SELECT id, pdb.score(id) AS bm25_score
FROM chunks
WHERE sanitized_text ||| :query
ORDER BY bm25_score DESC
LIMIT :bm25_top_k;

-- Dense candidate generation through pgvector.
SELECT chunk_id, embedding <=> :query_embedding AS distance
FROM embeddings
WHERE embedding_model_id = :embedding_model_id
ORDER BY embedding <=> :query_embedding
LIMIT :vector_top_k;
```

### CLI And Optional API

- Typer for CLI commands.
- Rich for terminal output.
- FastAPI only for machine access if needed.
- MCP Python SDK for agent-facing retrieval tools.
- Pydantic for configuration and payload validation.

Initial CLI commands:

```text
idp-brain sources list
idp-brain ingest run
idp-brain ingest status
idp-brain retrieve query
idp-brain retrieve explain
idp-brain eval run
idp-brain db migrate
idp-brain db reset
```

### MCP Server

The first agent-facing interface is an MCP server, similar in shape to documentation retrieval tools such as Context7.

The MCP server is read-only in the MVP. It exposes retrieval and citation tools, not ingestion mutation or database administration.

Implementation:

- Use the MCP Python SDK.
- Start with stdio transport for local agent integration.
- Add HTTP transport only after authentication and deployment policy are defined.
- MCP tools call the same internal retrieval service as the CLI.
- MCP tools never expose direct SQL or vector-store access.

Initial MCP tools:

- `search`: hybrid evidence retrieval over exact, BM25, and vector results.
- `fetch`: fetch a specific cited source span, chunk, artifact locator, or versioned source reference by ID.
- `explain_search`: score breakdown and selected/competing evidence diagnostics.
- `list_sources`: show indexed sources, versions, freshness, and visibility metadata.

The `search` tool input schema must include:

- `query`
- optional `source_ids`
- optional `source_types`
- optional `version`
- optional `time_or_release_range`
- optional `caller_context_hint`
- optional `include_conflicts`
- optional `max_results`
- optional `token_budget`

The `fetch` tool input schema must include:

- `citation_id`, `chunk_id`, or `artifact_id`
- optional `source_version_id`
- optional `line_range`
- optional `token_budget`

The `search` tool returns evidence bundle summaries and citation IDs. The `fetch` tool returns sanitized evidence content for a specific citation or locator. Neither tool may return raw unsanitized chunks or bypass corpus eligibility filters. Caller-provided context is only a hint; trusted source scope, license policy, sensitivity policy, redaction status, and version scope are derived by the server.

Optional Phase 6 CLI commands:

```text
idp-brain eval synthesize
idp-brain embeddings tune
idp-brain embeddings compare
```

### Extraction And Validation Tools

The exact extractor set is configurable per source. The initial repository should support these generic extractor families:

- Git source acquisition:
  - `git` CLI for clone, fetch, diff, tag, branch, commit, and ancestry metadata.
  - forge API enrichment only when credentials are configured.
- Repository discovery:
  - GitHub Linguist for language, generated-file, and vendored-file classification.
  - configured include/exclude rules for source-specific overrides.
- Source code extraction:
  - tree-sitter for AST-aware chunks and symbol boundaries.
  - language-native commands where configured, starting with Go: `go list`, `go doc`, `go mod graph`, and `go test -list`.
  - Semgrep for optional static pattern extraction.
- Documentation extraction:
  - `markdown-it-py` for Markdown.
  - `beautifulsoup4` with `lxml` for HTML.
  - Docling for local-first rich document conversion.
  - Apache Tika for broad text and metadata extraction.
  - Unstructured for element-aware document segmentation.
- Schema and API extraction:
  - Python `json` and `tomllib` for native structured formats.
  - PyYAML or `ruamel.yaml` for YAML.
  - `jsonschema` for JSON Schema validation and traversal.
  - `openapi-spec-validator` for OpenAPI validation.
- Repository digest fallback:
  - Gitingest for coarse repository context, unknown languages, smoke tests, and debugging only.
- Security and compliance:
  - Gitleaks or detect-secrets for secret-like values.
  - Microsoft Presidio for PII detection and anonymization profiles.
  - ScanCode Toolkit and OSS Review Toolkit for license and origin metadata.

Validation tools:

- ruff
- mypy
- pytest
- yamllint
- actionlint
- shellcheck

Domain validators such as `kubectl`, `helm`, `kustomize`, `flux`, or `kubeconform` can be added as optional configured validators. They are not part of the core retrieval architecture.

## Configuration Model

The pipeline is configured through versioned files.

Required configuration:

- `config/sources.yaml`: source catalog.
- `config/extractors.yaml`: extractor profiles.
- `config/models.yaml`: embedding, reranker, generator, model-serving, and provider-routing profiles.
- `config/retrieval.yaml`: retrieval, ranking, and embedding settings.
- `config/evaluation.yaml`: retrieval evaluation and optional embedding fine-tuning settings.
- `config/security.yaml`: redaction, source allowlist, and prompt-injection handling rules.
- `config/corpus.yaml`: corpus eligibility defaults for source allowlists, visibility labels, sensitivity labels, and license policy labels. It does not define per-caller retrieval rules in the MVP.
- `config/memory.yaml`: memory scopes, retention, promotion rules, and retrieval influence limits.

`config/sources.yaml` defines each source:

- stable source ID
- source type
- repository URL or artifact URL
- tracked refs, tags, branches, or release channels
- version strategy: tags, releases, branches, semver, calendar versions, or explicit refs
- include paths
- exclude paths
- extractor profile
- source priority
- visibility label
- sensitivity class
- license policy
- refresh cadence

Example source types:

- `git_repository`
- `git_repository_digest`
- `release_artifact`
- `documentation_site`
- `documentation_file`
- `openapi_spec`
- `schema_bundle`
- `local_directory`

No source type may require code changes just to add a new tool. Code changes are allowed only when a new extractor family is needed.

`config/retrieval.yaml` defines named query profiles:

- `docs_qa`: documentation-first retrieval with BM25 and dense candidates over narrative chunks, headings, examples, tables, and release notes.
- `code_qa`: code-first retrieval with exact symbol lookup, path lookup, AST chunks, code embeddings, and documentation backfill.
- `api_symbol_lookup`: exact names, symbols, fields, endpoint paths, schema keys, and signature text before broader semantic search.
- `release_change_search`: version lineage, changelog, commit, tag, release, and diff-aware retrieval.
- `conflict_search`: structured claim and conflict retrieval with competing evidence included.

Each profile configures exact lookup fields, BM25 fields, vector index, embedding model, candidate counts, fusion method, reranker, freshness weighting, authority weighting, and token budget.

## Source Authority Model

Authority is configurable per source and per artifact type.

Default authority order:

1. Generated schemas and formal API definitions.
2. Source code.
3. Tests and examples.
4. Release notes and changelogs.
5. Documentation.

This order can be overridden in `config/retrieval.yaml`. For example, Kubernetes documentation may be configured as authoritative for Kubernetes API behavior, while source code may be authoritative for fast-moving upstream tools.

When two indexed sources conflict, retrieval must return both sides with provenance and mark the conflict instead of silently merging them.

## Claim Model And Conflict Detection

Structured extractors may emit normalized claims. Claims make conflict detection implementable without hardcoding any specific tool domain.

Minimum claim shape:

- subject: stable identifier for the entity being described.
- predicate: property, capability, relationship, or behavior.
- value: normalized scalar, object, or reference.
- value type: string, number, boolean, enum, object, relationship, or text.
- scope: version, source, path, language, platform, or environment constraints.
- confidence: extractor confidence and source authority.
- evidence: one or more citations.

Conflict detection compares claims with the same subject, predicate, and overlapping scope. A conflict exists when values are incompatible and neither claim is simply older, narrower, or lower authority under configured precedence rules.

Conflicts are stored, not resolved silently. Retrieval may rank one side higher, but the evidence bundle must expose the competing claims when both are relevant.

## Relationship And Lineage Retrieval

Relationship retrieval is implemented from normalized PostgreSQL tables, not from a separate traversal store.

The relational model must support traversals that dense vector search handles poorly, such as:

- source -> artifact -> symbol -> claim -> citation
- change -> version -> affected artifact -> affected claim
- package -> dependency -> transitive dependency
- schema -> field -> validation rule -> example
- claim -> conflicts_with -> claim

Rules:

- Relational tables are canonical.
- Relationship records are normalized, typed, versioned, and citation-backed.
- Relationship queries must return citation-backed entity IDs, not uncited free text.
- Traversal depth and result count are bounded by configuration.
- Retrieval uses relationship results as candidates or ranking signals, then still returns evidence bundles.

Initial relationship types:

- `contains`
- `defines`
- `references`
- `derived_from`
- `cites`
- `introduced_in`
- `removed_in`
- `changed_by`
- `conflicts_with`

## Memory Layer

The architecture includes a memory layer, but memory is not part of the authoritative source corpus.

Memory stores durable interaction knowledge that improves future retrieval and agent behavior:

- user and project preferences
- accepted architecture decisions
- rejected approaches
- source catalog decisions
- retrieval feedback
- known evaluation failures
- recurring corrections
- useful query rewrites

Memory must not store raw upstream source facts as truth. If a memory item describes tool behavior, it must link to citations or be treated as a user/project note rather than evidence.

Memory scopes:

- `session`: temporary context for one interaction.
- `project`: durable decisions and preferences for this repository.
- `user`: user-specific preferences, only when explicitly allowed.
- `system`: curated operational rules shipped with the repository.

Memory item types:

- `preference`
- `decision`
- `correction`
- `retrieval_feedback`
- `evaluation_observation`
- `source_policy`
- `workflow_note`

Memory rules:

- Memory writes require explicit promotion from a conversation, evaluation result, or operator action.
- Untrusted source text cannot write memory.
- Memory is subject to redaction, corpus eligibility, and retention policy.
- Memory can affect query expansion, source ranking, and tool behavior.
- Memory cannot override higher-authority source evidence.
- Memory items must be inspectable, editable, and deletable.
- Expired memory must not be used for retrieval or agent behavior.

## Version And Change Lineage

The pipeline must track which changes are present in which versions.

For Git-based sources, the first implementation should derive lineage from local repository data:

- tags
- release branches
- commit ancestry
- merge commits
- file diffs

When configured credentials are available, the pipeline may enrich lineage with remote forge metadata:

- pull request number and title
- merge timestamp
- linked issues
- release notes
- changelog entries

The retriever must support questions like:

- Which version introduced this symbol, field, endpoint, or behavior?
- Which release first contained this commit or pull request?
- What changed between two versions?
- Is this source fact current, removed, or only present in older releases?

Lineage is evidence, not guesswork. If the pipeline cannot prove the first containing version, it must mark the value as unknown.

## Pipeline Architecture

The RAG pipeline has ten stages. Each stage writes normalized records and diagnostics so failures can be replayed without guessing which tool produced which output.

1. **Receive**
   - Tools: Pydantic settings, `config/sources.yaml`, `config/extractors.yaml`, `config/corpus.yaml`, Typer CLI.
   - Read source definitions, extractor profiles, corpus eligibility policy, and refresh policy.
   - Resolve refs, tags, release artifacts, and local source paths.
   - Create an `ingestion_runs` record before network or filesystem work begins.

2. **Fetch**
   - Tools: `git` CLI, HTTP download client, checksum verifier, optional forge API client.
   - Clone or update repositories.
   - Download release artifacts, documentation bundles, schema bundles, or local directory snapshots.
   - Record commit SHAs, tags, branches, checksums, timestamps, remote URLs, and fetch errors.
   - Build a version map from tags, releases, branches, and commit ancestry.

3. **Discover**
   - Tools: GitHub Linguist, configured include/exclude rules, MIME/type detection, checksum hashing.
   - Classify files by source type, language, generated/vendored status, artifact role, and extractor profile.
   - Exclude generated and vendored files by default for code retrieval.
   - Preserve override decisions as auditable discovery records.

4. **Extract**
   - Tools for code: tree-sitter, language-native commands, Semgrep rules where configured.
   - Tools for docs: `markdown-it-py`, `beautifulsoup4`/`lxml`, Docling, Apache Tika, Unstructured.
   - Tools for schemas: Python `json` and `tomllib`, PyYAML or `ruamel.yaml`, `jsonschema`, `openapi-spec-validator`.
   - Tool for repository digest fallback: Gitingest.
   - Extract structured facts, symbols, headings, sections, tables, code blocks, schema paths, examples, and citations.
   - Preserve source provenance for every fact and candidate chunk.

5. **Redact, Classify, And Check Policy**
   - Tools: configured regex rules, Gitleaks or detect-secrets, Microsoft Presidio, source allowlist policy, license policy.
   - Detect secret-like values, credentials, tokens, PII, and configured sensitive patterns.
   - Redact before chunking, embedding, persistence, retrieval logs, evaluation data, or LLM context assembly.
   - Assign sensitivity labels, visibility labels, license policy labels, redaction status, and source allowlist status.
   - Store redaction markers and counts, not raw secret or PII values.

6. **Normalize**
   - Tools: Pydantic domain models, SQLAlchemy ORM/Core, normalized metadata schema.
   - Convert extractor output into common internal models for artifacts, facts, claims, relationships, chunks, citations, and memory links.
   - Assign source type, authority rank, parser version, freshness metadata, license metadata, and sanitized content hashes.
   - Link facts and chunks to versions, commits, tags, releases, and checksums that prove membership.

7. **Chunk**
   - Tools: tree-sitter symbol boundaries, LlamaIndex node abstractions, document heading/table/code-block splitters.
   - Use class/function/method/type/interface boundaries for source code.
   - Use heading paths, anchors, tables, lists, and code blocks for documentation.
   - Keep package, namespace, file path, symbol path, signature, imports, heading path, and parent context attached to each chunk.
   - Keep chunk boundaries stable across incremental updates.

8. **Embed, Store, And Index**
   - Tools: configured embedding provider from `config/models.yaml`, PostgreSQL, SQLAlchemy, Alembic, pgvector, ParadeDB `pg_search`.
   - Generate embeddings only for changed sanitized chunks.
   - Store structured facts, relationships, claims, chunks, citations, and retrieval metadata in PostgreSQL.
   - Store vectors in pgvector with separate logical indexes for docs, code, memory, and model versions.
   - Build or refresh ParadeDB BM25 indexes for sanitized chunks and selected metadata.
   - Use `COPY` or batched inserts for bulk loads, then build or rebuild derived indexes as migration-managed artifacts.

9. **Retrieve**
   - Tools: PostgreSQL exact indexes, PostgreSQL B-tree/partial/trigram indexes, ParadeDB `pg_search`, pgvector, rank fusion, reranker service.
   - Apply source allowlist, license, sensitivity, redaction, version, and active-index filters before every subquery.
   - Run exact lookup for identifiers, symbols, paths, versions, fields, endpoint paths, and error strings.
   - Run BM25 candidate generation through `pg_search`.
   - Run dense candidate generation through pgvector exact search, HNSW, or configured IVFFlat indexes.
   - Run bounded relationship traversal for lineage, dependency, conflict, and impact queries.
   - Fuse candidates with reciprocal-rank fusion or configured weighted fusion, then rerank.
   - Return evidence bundle summaries and citation IDs.

10. **Evaluate, Operate, And Tune**
   - Tools: pytest fixtures, LlamaIndex retrieval evaluation utilities, Ragas, DeepEval, OpenTelemetry, Prometheus, postgres_exporter.
   - Measure retrieval separately from generated answer quality.
   - Track Recall@k, MRR, nDCG@10, hit rate, context precision, context recall, latency, and abstention behavior.
   - Compare BM25-only, vector-only, exact-only, and fused hybrid retrieval.
   - Generate synthetic query-context pairs only from approved chunks and only as evaluation or training data.
   - Fine-tune embeddings only as an experiment after baseline retrieval and held-out thresholds prove the need.
   - Promote a tuned embedding model only when held-out metrics improve without redaction, freshness, citation, corpus eligibility, or lineage regressions.

## Data Model

Postgres stores structured metadata and facts. pgvector stores embeddings. ParadeDB `pg_search` provides BM25 indexes over sanitized chunks and selected metadata.

Core tables:

- `sources`: configured source definitions.
- `source_versions`: resolved commits, tags, artifact versions, and checksums.
- `source_changes`: commits, pull requests, merge commits, release entries, and changelog entries when available.
- `change_versions`: mapping from a change to the versions, tags, or releases that contain it.
- `artifact_versions`: mapping from artifacts to versions, tags, releases, and first/last membership.
- `chunk_versions`: mapping from retrievable chunks to versions, tags, releases, and first/last membership.
- `fact_versions`: first seen version, last seen version, and current version membership for extracted facts.
- `corpus_policy_defaults`: configured global retrieval eligibility defaults for invited users. This table does not model per-caller visibility.
- `redaction_events`: redaction rule matches, marker counts, and affected artifact/chunk IDs without raw secret values.
- `ingestion_runs`: one record per pipeline run.
- `artifacts`: discovered files, schemas, specs, docs, examples, and generated artifacts.
- `artifact_extractions`: parser output records with extractor name, extractor version, parser profile, and extraction diagnostics.
- `facts`: structured facts extracted from artifacts.
- `claims`: normalized subject/predicate/value statements derived from facts.
- `claim_versions`: version membership for claims.
- `claim_conflicts`: detected incompatible claims with overlap scope and supporting citations.
- `relationships`: typed, versioned, citation-backed links between normalized entities.
- `relationship_versions`: version membership for relationships.
- `license_findings`: license IDs, copyright notices, scanner provenance, and policy status.
- `memory_items`: promoted memory records with scope, type, owner, retention, confidence, and provenance.
- `memory_events`: creation, promotion, update, expiry, and deletion audit events.
- `memory_links`: links from memory items to citations, retrieval events, eval results, or decisions.
- `memory_embeddings`: optional vectors for memory items that are safe for semantic recall.
- `chunks`: retrievable text/code/schema chunks.
- `embeddings`: vector records for chunks.
- `embedding_models`: configured embedding providers and promoted model versions.
- `embedding_jobs`: asynchronous embedding work units, input hashes, provider responses, failures, and retry state.
- `index_versions`: blue/green retrieval index versions for BM25, vector, exact, and relationship-derived retrieval artifacts.
- `citations`: stable pointers to source evidence.
- `retrieval_events`: query, filters, selected chunks, and ranking diagnostics.
- `eval_cases`: regression questions and expected evidence.
- `eval_results`: retrieval and answer-quality results over time.
- `finetuning_runs`: optional embedding tuning experiments, datasets, metrics, and promotion decisions.

BM25 indexes are migration-managed indexes over canonical tables, not a second source of truth. The initial BM25 index should cover:

- sanitized chunk text
- chunk title or heading path
- symbol path and signature text when available
- artifact path and source type
- language and artifact role
- version, tag, or release labels when useful for ranked search
- visibility and sensitivity fields when ParadeDB filter pushdown is required

Vector indexes are also derived retrieval structures. Each promoted embedding model and distance function gets its own explicit index definition. HNSW is the default ANN index for broad semantic retrieval; exact search remains available for filtered subsets and correctness checks.

Every BM25 index, vector index, embedding model, chunking profile, and reranker profile belongs to an `index_versions` record. New corpus builds are written into an inactive index version first, evaluated, then activated atomically through configuration or a database flag. Rollback means reactivating the previous index version, not mutating rows in place.

Every artifact, fact, chunk, and citation must include:

- source ID
- source version ID
- repository or artifact URL
- commit SHA, tag, version, or checksum
- first containing version, when known
- last containing version, when known
- path or logical locator
- source type
- license ID and license policy status, when known
- visibility label
- sensitivity class
- redaction status
- extractor name and version
- extractor profile
- sanitized content hash
- first seen timestamp
- last verified timestamp

Fetched source versions may store upstream commit SHAs, release checksums, and artifact checksums for provenance. Stored chunks, facts, embeddings, retrieval events, and LLM context must use sanitized content only. Raw fetched content may exist in a local ingestion cache, but it is outside source control, may be deleted after ingestion, and is never embedded.

Every memory item must include:

- memory ID
- scope
- type
- owner or project label
- visibility label
- sensitivity class
- provenance
- confidence
- retention or expiry
- promotion reason
- redaction status
- created and last reviewed timestamps

## Retrieval Architecture

Retrieval is hybrid and evidence-first.

Query profiles are selected before candidate generation:

- `docs_qa`: narrative docs, examples, tables, release notes, and generated API docs.
- `code_qa`: exact symbol/path lookup, tree-sitter chunks, code embeddings, imports, signatures, and nearby docs.
- `api_symbol_lookup`: exact and lexical lookup for API fields, endpoint paths, flags, class names, methods, functions, errors, and version strings.
- `release_change_search`: release notes, changelogs, commits, tags, diffs, first-seen and last-seen version membership.
- `conflict_search`: normalized claims and competing evidence.

Retrieval stages:

1. Parse query intent, query profile, source scope, version scope, and hard filters.
2. Derive trusted corpus eligibility from local configuration and stored source metadata. Caller hints never expand retrieval scope.
3. Apply source allowlist, license, sensitivity, redaction, version, and active-index filters to every subquery.
4. Load relevant memory items allowed by the same corpus eligibility rules.
5. Run exact lookup for names, symbols, versions, field names, endpoint paths, errors, paths, and identifiers using B-tree, partial, and trigram indexes.
6. Run ParadeDB BM25 search with `pg_search` over the profile-specific BM25 fields.
7. Run pgvector similarity search:
   - exact search for small filtered subsets
   - HNSW ANN for broad dense retrieval
   - IVFFlat only for configured indexes that justify the tradeoff
8. Run bounded relationship traversal from normalized tables when query intent needs lineage, dependencies, conflicts, or impact.
9. Merge candidates with reciprocal-rank fusion or configured weighted fusion. Default candidate generation starts with 50 to 200 BM25 candidates and 50 to 200 vector candidates per profile, then tunes from evaluation data.
10. Rerank fused candidates by:
   - semantic relevance
   - lexical match strength
   - source authority
   - version match
   - change/version lineage
   - relationship path relevance
   - allowed memory preference or feedback
   - freshness
   - citation completeness
11. Return an evidence bundle.

The retriever must expose why a chunk was selected. Debug output should include score components, rank positions, source metadata, filters applied, index path used, query profile, active index version, and competing candidates. BM25 scores and vector distances must not be compared directly without rank fusion or calibration.

Reranking is a separate service call, not a database concern. The default local rerankers are BGE reranker v2 m3 or Jina Reranker v2 multilingual. Reranking receives only sanitized candidate text and metadata that has passed corpus eligibility checks.

## Embedding Tuning Policy

Embedding fine-tuning is a retrieval optimization lane, not the default RAG path.

Allowed process:

1. Build the baseline index with the configured embedding provider.
2. Create a retrieval evaluation dataset from human-authored cases and optional synthetic query-context pairs.
3. Keep a held-out test set that is never used for training.
4. Run baseline retrieval metrics, at minimum hit rate and MRR.
5. Fine-tune a local embedding model only if baseline retrieval is the bottleneck.
6. Re-index into a separate experiment namespace.
7. Compare baseline and tuned retrieval on the same held-out set.
8. Promote the tuned model only through an explicit configuration change.

Rules:

- Synthetic questions are training and evaluation data only.
- Synthetic questions are never authoritative evidence.
- Chunks containing secrets or disallowed sources cannot be used for tuning.
- Fine-tuning output must be versioned and reproducible.
- The baseline embedding provider must remain available for rollback.

## Evidence Bundle Contract

The retriever returns evidence bundles, not raw untrusted context.

Each evidence bundle contains:

- query
- normalized query intent
- selected chunk IDs and sanitized excerpts
- selected memory item IDs and sanitized summaries, when used
- citations
- source authority ranking
- freshness metadata
- conflict markers
- corpus eligibility filter result
- redaction status
- token budget estimate

Each citation contains:

- source ID
- source URL
- commit, tag, version, or checksum
- path or locator
- line range when available
- source type
- sanitized content hash
- redaction status
- visibility label

LLM-facing context is built from evidence bundles after redaction and policy checks.

## Security Model

Security applies before storage and before retrieval context reaches an LLM.

Rules:

- Secret-looking values are redacted before chunking, embedding, storage, retrieval logs, and LLM context assembly.
- Raw secrets are never intentionally stored in Postgres, pgvector, retrieval logs, evaluation datasets, or generated context.
- PII detection runs before embeddings for source profiles that may contain names, email addresses, issue text, commit metadata, or support artifacts.
- License detection runs during ingestion and writes policy status into metadata before chunks become retrievable.
- Raw fetched files may exist only in local ingestion cache storage and must be deletable without data loss.
- Source allowlists are enforced before retrieval.
- License, sensitivity, redaction, version, and active-index filters run before LLM context assembly.
- Corpus eligibility labels are stored on sources, artifacts, chunks, claims, and citations.
- License policy labels are stored on sources, artifacts, chunks, claims, and citations.
- Memory writes require explicit promotion and audit events.
- Memory retrieval uses the same corpus eligibility and redaction policy as source retrieval.
- Documentation, examples, and comments are treated as untrusted input.
- Prompt-injection-like text in sources is stored as data, never obeyed as instruction.
- Retrieval logs must not leak secrets or full sensitive chunks.

## Operations And Observability

Observability is vendor-neutral and starts with OpenTelemetry.

Required spans:

- request receipt
- corpus eligibility derivation
- query profile selection
- exact lookup
- ParadeDB BM25 retrieval
- pgvector retrieval
- relationship traversal
- fusion
- reranking
- evidence packaging
- MCP `search` or `fetch`
- optional LLM call

Required metrics:

- ingestion runs, changed chunks, failed chunks, redacted chunks, and embedding job failures
- BM25, vector, exact, relationship, reranker, and total retrieval latency
- candidate counts before and after filtering, fusion, and reranking
- PostgreSQL connection, WAL, replication, lock, index, and query metrics
- recall, MRR, nDCG, hit rate, context precision, context recall, and abstention regression metrics

Initial operations tools:

- OpenTelemetry SDK and Collector for traces, logs, and metrics.
- Prometheus for metrics collection.
- postgres_exporter and `pg_stat_statements` for PostgreSQL observability.
- OpenLLMetry only when LLM-call telemetry is needed.
- Grafana dashboards once Prometheus metrics are stable.

PostgreSQL must be operated with normal production safety when moved beyond local development: backups, PITR, WAL archiving, restore verification, extension-version tracking, migration rollback plans, and at least one read replica when read load or recovery objectives require it.

Long-running ingestion and refresh jobs start as repository-owned Python workers. If retry, resume, compensation, and long-running workflow guarantees become hard requirements, use Temporal. LangGraph may be used for agent/workflow orchestration, but it does not replace the retrieval service or the database.

## Local Runtime

`docker-compose.yaml` runs local Postgres with pgvector and ParadeDB `pg_search`.

Required service:

- `postgres`

The `postgres` service must use a custom image or approved image that includes pgvector and ParadeDB `pg_search`, then enable `vector`, `pg_search`, and `pg_trgm` through migrations or initialization scripts.

The local database is disposable. Alembic migrations must recreate schema state from scratch.

Local startup is not considered healthy until an extension smoke test creates `vector`, `pg_search`, and `pg_trgm`, creates one BM25 index, creates one HNSW vector index, inserts fixture rows, and runs one BM25 query plus one vector query.

## Mise Tasks

Required tasks:

```text
mise run install
mise run up
mise run down
mise run db:migrate
mise run db:reset
mise run ingest
mise run retrieve -- <query>
mise run eval
mise run lint
mise run test
mise run ci
```

Tasks may call internal Python modules, but `mise` is the documented interface.

Optional Phase 6 tasks:

```text
mise run eval:synthesize
mise run embeddings:tune
mise run embeddings:compare
```

## GitHub Actions

Initial workflows:

- `ci.yaml`: lint, typecheck, tests, migration check, extension smoke test.
- `ingest.yaml`: scheduled and manual ingestion validation against an ephemeral database.
- `eval.yaml`: retrieval regression suite.
- `dependency-review.yaml`: dependency and license review.

GitHub Actions provides recurring compute for validation, extraction tests, regression checks, and optional exported index snapshots. With the default local-only Postgres runtime, Actions must not assume durable access to the server database. Durable local ingestion runs through `mise` on the server, or through a later explicitly configured remote database/import workflow.

Scheduled ingestion in Actions is validation-only until the repository defines export/import format, retention, artifact encryption, restore checks, and explicit promotion into an active `index_versions` record.

The same tasks must run locally through `mise`.

## Evaluation

The project must test retrieval quality before testing generated answers.

Evaluation sources:

- golden human-authored questions from real maintainer, operator, or developer workflows
- synthetic query-context pairs generated only from approved chunks
- regression fixtures for known failures and accepted architecture decisions

Required retrieval metrics:

- Recall@k
- MRR
- nDCG@10
- hit rate
- p50 and p95 latency by retrieval stage
- abstention correctness when evidence is missing

Optional answer-quality metrics:

- faithfulness
- answer relevancy
- context precision
- context recall
- hallucination rate

Required evaluation categories:

- exact identifier lookup
- source-code lookup
- schema/API lookup
- documentation lookup
- release/version lookup
- change-to-version lookup
- version diff retrieval
- source-vs-doc conflict retrieval
- stale source detection
- retrieval with source filters
- retrieval with token budget limits
- BM25-only, vector-only, and fused hybrid retrieval comparisons
- secret redaction
- PII redaction
- license policy filtering
- hit rate, Recall@k, MRR, and nDCG regression tracking

Optional Phase 6 evaluation categories:

- synthetic query-context dataset quality
- baseline versus tuned embedding comparison

`config/evaluation.yaml` must define thresholds before a gate is release-blocking. Until thresholds exist, evaluation failures are reported as diagnostics, not as release approval or rejection.

Release gates:

- no secret leakage into embeddings
- no disallowed PII leakage into embeddings, logs, eval data, or LLM context
- no uncited answer context
- no retrieval regression on fixture questions
- no false first-version claim when lineage is unknown
- no stale source selected when a fresher matching source exists
- no ignored source conflict when conflicting evidence is present
- no tuned embedding promotion without held-out metric improvement

## Phase Plan

### Phase 1: Skeleton And Local Runtime

- Add `mise.toml`.
- Add `docker-compose.yaml`.
- Add Python project and `uv.lock`.
- Add Alembic migrations.
- Add extension smoke test for `vector`, `pg_search`, `pg_trgm`, one BM25 index, and one HNSW index.
- Add CLI command skeleton.
- Add CI workflow.

### Phase 2: Generic Ingestion

- Implement source catalog loading.
- Implement corpus eligibility policy loading.
- Implement git repository fetcher.
- Implement artifact discovery.
- Store source versions, artifacts, and ingestion runs.
- Build tag, release, commit, and change lineage tables.

### Phase 3: Extraction And Chunking

- Implement text, Markdown, YAML, JSON, TOML, OpenAPI, JSON Schema, and tree-sitter extractors.
- Implement redaction and sensitivity classification before persistence.
- Add content hashing and incremental update detection.
- Store sanitized chunks, citations, claims, and claim conflicts.

### Phase 4: Embeddings, Hybrid Retrieval, And MCP

- Add configurable embedding provider.
- Store vectors in pgvector.
- Add HNSW indexes for broad vector retrieval and exact vector fallback for selective filters.
- Add ParadeDB BM25 indexes for sanitized chunks and selected metadata.
- Implement exact, BM25, and vector retrieval.
- Implement rank fusion, reranking, diagnostics, and evidence bundle assembly.
- Implement bounded relationship traversal for lineage, dependency, conflict, and impact queries.
- Add read-only MCP `search`, `fetch`, `explain_search`, and `list_sources` tools.

### Phase 5: Evaluation And Operations

- Add retrieval regression cases.
- Define release-blocking thresholds in `config/evaluation.yaml`.
- Add scheduled ingestion.
- Add freshness metrics.
- Add retrieval diagnostics.
- Add OpenTelemetry traces and Prometheus metrics for the retrieval stages.
- Add security/redaction tests.
- Add PII and license-policy tests.
- Add explicit memory promotion, listing, expiry, deletion, and audit events.
- Add memory-aware retrieval reranking guarded by corpus eligibility and retention policy.

### Phase 6: Optional Embedding Tuning

- Generate synthetic query-context pairs from approved chunks.
- Split train, validation, and held-out test datasets.
- Run baseline hit rate and MRR.
- Fine-tune local embeddings as an experiment.
- Promote tuned embeddings only when held-out metrics improve and safety gates pass.

## Findings Addressed

The architecture is intentionally focused on the RAG receiver, pipeline, and retriever. Tool-specific intelligence is data, not architecture. A platform-tool catalog can be added later through configuration, but the core must remain useful for any source-backed technical tooling domain.

The review findings are resolved as architecture constraints:

| Finding | Architecture response |
| --- | --- |
| Keep the first milestone narrow. | The first useful milestone is sanitized ingestion, citations, corpus-safe exact/BM25/vector retrieval, MCP `search` and `fetch`, and retrieval fixtures. Memory, fine-tuning, advanced workflows, and answer generation are later or optional. |
| Make ParadeDB `pg_search` + pgvector the target retrieval store. | PostgreSQL 18 with `pg_search`, pgvector, and `pg_trgm` is the named target. BM25 and vector indexes are migration-managed derived indexes over relational records. Extension, BM25, and HNSW smoke tests are required locally and in CI. |
| Verify custom image and extension compatibility. | The local runtime must use an approved or repository-owned image that can create `vector`, `pg_search`, and `pg_trgm`, then create fixture BM25 and HNSW indexes before the service is considered healthy. |
| Enforce corpus eligibility filters before every query. | Retrieval stages apply source allowlist, sensitivity, license, redaction, version, and active-index filters before exact lookup, BM25, vector search, relationship traversal, memory lookup, diagnostics, and MCP `fetch`. |
| Do not trust caller-provided MCP context. | MCP `caller_context_hint` is only a hint. Corpus eligibility is derived from trusted local configuration and stored source metadata. |
| Return sanitized evidence only. | MCP and CLI return evidence bundle summaries, citation IDs, sanitized excerpts, and diagnostics. Raw unsanitized chunks are never returned, embedded, logged, or sent to rerankers or LLMs. |
| Limit claim/conflict detection until comparator rules exist. | Claims are produced only by structured extractors. Conflict detection is limited to normalized subject, predicate, value, and overlapping scope with explicit comparator rules. |
| Do not infer unknown version lineage. | First/last containing versions are evidence-backed fields. Unknown lineage remains unknown and is exposed as such in retrieval results. |
| Keep GitHub Actions validation-first while the durable database is local-only. | Actions run lint, tests, migrations, extension smoke tests, ingestion validation, and evals against ephemeral databases. Scheduled ingestion snapshots require explicit export/import, encryption, retention, restore checks, and index promotion rules. |
| Define fixtures and thresholds before release-blocking gates. | `config/evaluation.yaml` must define metric thresholds before gates block a release. Until then, evaluation output is diagnostic. |
