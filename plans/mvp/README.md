# MVP Implementation Plan

This README is the operating guide for the `idp-brain` MVP plan. It is written
for IT implementers and coding agents who may not already know RAG terminology.
Use it as the top-level map, then follow each step file exactly.

The plan builds a local-first retrieval system, not a chatbot, not a web app,
and not a model fine-tuning project. The first useful product is a pipeline
that can read configured technical sources, remove or classify sensitive
content before storage, index the safe evidence, and return citation-backed
results through CLI and read-only MCP tools.

If these terms are new: RAG is short for Retrieval-Augmented Generation; in
this plan it means "retrieve the right evidence before an answer is written."
Local-first means the useful development path runs on a workstation and in CI
without required hosted services; CLI means terminal commands; CI means
automated checks such as GitHub Actions; corpus eligibility means the source,
license, sensitivity, redaction, and version rules that decide which records
can be retrieved; LLM means large language model; MCP means a read-only local
tool protocol that agents can call.

## MVP Goal And Boundaries

Build the first useful `idp-brain` milestone described in `ARCHITECTURE.md`: a
local-first Python 3.14 RAG pipeline that ingests configured sources, persists
only sanitized evidence, indexes it with PostgreSQL 18, ParadeDB `pg_search`,
and pgvector, and exposes corpus-safe retrieval through CLI and read-only MCP
tools.

The MVP ends when sanitized ingestion, citations, source/license/sensitivity/redaction-safe
exact/BM25/vector retrieval, evidence bundles, MCP `search`, `fetch`,
`explain_search`, and `list_sources`, retrieval evaluation, and basic operations
telemetry work locally and in CI.

Out of scope for the MVP: memory UX, embedding fine-tuning, production high
availability, remote model serving, answer generation, developer portal, and
any hardcoded platform-tool catalog.

## Plain-Language Project Overview

`idp-brain` is an evidence retrieval service for technical knowledge. It is
meant to answer questions like "which source says this?", "which version
introduced this?", or "what snippets should an LLM read before answering?"
without trusting stale model memory.

The system works with configured sources. A source can be a Git repository, a
local directory, documentation files, release artifacts, schemas, API specs, or
other configured inputs. Adding a new tool or project should normally mean
changing configuration and source data, not hardcoding that tool into the
retrieval engine.

The basic data flow is:

1. Read source configuration.
2. Acquire or inspect the configured source.
3. Extract useful text, metadata, symbols, claims, and citations.
4. Redact secrets and classify sensitivity, visibility, source eligibility, and license
   status before anything is persisted.
5. Store sanitized chunks, citations, metadata, lineage, and retrieval records
   in PostgreSQL.
6. Build exact lookup, BM25 keyword, and vector search indexes over sanitized
   records.
7. Filter every query by trusted corpus eligibility rules before searching.
8. Merge and rerank allowed candidates.
9. Return an evidence bundle with sanitized excerpts, citation IDs, source
   metadata, diagnostics, and conflict markers where needed.
10. Expose the same retrieval behavior through CLI commands, read-only MCP
    tools, evaluation jobs, and basic telemetry.

## What RAG Means In This Project

RAG means Retrieval-Augmented Generation. In many products, RAG means an app
retrieves documents and sends them to a generative model so the model can write
an answer. In this MVP, the project stops before answer generation. The output
is safe, citation-backed evidence that a human, agent, or later LLM-facing
system can use.

The important terms in this plan are:

- Retrieval: finding relevant records from the indexed source corpus.
- Augmentation: packaging the selected evidence with citations and metadata so
  another system has reliable context.
- Generation: producing a final natural-language answer. This is out of scope
  for the MVP.
- LLM: large language model. The MVP may provide evidence for a later LLM
  system, but it does not ask an LLM to write answers.
- Local-first: the normal development and CI path runs with repository-owned
  code, local services, and deterministic test doubles instead of required paid
  model APIs or private hosted services.
- CLI: command-line interface. These are terminal commands for operators and
  implementers.
- CI: continuous integration. In this plan it mainly means GitHub Actions jobs
  that run checks in a clean environment.
- Corpus eligibility: the server-side source allowlist, license, sensitivity,
  redaction, version, and active-index policy that decides which source records
  are retrievable. In this MVP every invited user can see the same approved
  corpus; there is no per-caller or role-based filtering
  control.
- Source allowlist: the configured list of sources a query is allowed to use.
  It prevents one query from silently searching every known source.
- Sensitivity label: a classification such as public, internal, confidential,
  or restricted that controls whether content can be stored, indexed, returned,
  or used for diagnostics.
- License filter: a check that prevents the system from returning or using
  evidence in a way that violates the configured source license policy.
- Chunk: a small sanitized piece of source content, such as a section, code
  symbol, schema field, example, or extracted fact.
- Citation: the pointer that proves where a chunk came from, including source,
  version, path or locator, line range when available, redaction status, and
  visibility label.
- Lineage: the evidence-backed history for where a chunk, claim, symbol, or
  artifact came from, including known first and last versions when proven.
- Tombstone: a stored marker that says a previously seen source item is now
  deleted or unavailable, so retrieval does not treat old evidence as current.
- Exact lookup: searching for direct matches such as identifiers, file paths,
  flags, error strings, API names, or citation IDs.
- Embedding: a numeric representation of sanitized text used for semantic
  search. Embeddings are indexes, not evidence, and raw unsanitized text must
  never be embedded.
- BM25: keyword-style lexical ranking. It is useful for exact words,
  identifiers, paths, flags, errors, and API names.
- pgvector: PostgreSQL vector search used for semantic similarity over
  embeddings.
- ParadeDB `pg_search`: the PostgreSQL-based BM25 search layer used by this
  MVP.
- Reranker: a component that reorders already-filtered, sanitized candidates.
  It must not receive ineligible or raw unsanitized text.
- Evidence bundle: the safe retrieval response contract. It contains selected
  evidence, citation references, diagnostics, filters applied, freshness and
  authority metadata, and conflict information without leaking raw source text
  or hidden pre-filter details.
- MCP: Model Context Protocol. In this MVP it is a read-only local tool server
  for agents. It exposes retrieval tools only; it does not mutate ingestion,
  configuration, databases, or external systems.

## Execution Rules

- Complete steps in order.
- Make one focused commit per step.
- Do not skip tests or checks listed in a step.
- Keep implementation decisions aligned with `ARCHITECTURE.md`; do not
  re-decide the architecture in individual steps.
- Do not persist, embed, log, or return raw unsanitized chunks.
- Do not change unrelated product code while implementing a step.

Operationally, a step is not complete until its implementation instructions,
listed tests, and acceptance criteria all pass. If a test cannot be run because
the local environment is missing a required service, document that clearly in
the handoff instead of silently treating the step as done.

## Shared Constraints

- Raw unsanitized chunks are never persisted, embedded, logged, returned, or
  sent to rerankers or LLM-facing context.
- Deterministic local/mock embedding and reranking must work in CI without
  external API calls.
- Source allowlist, license, sensitivity, redaction, version, and active-index
  filters run before exact
  lookup, BM25, vector, relationship, memory, diagnostics, CLI output, and MCP
  fetch/search subqueries.
- Memory UX, embedding fine-tuning, production HA, and remote model serving are
  out of MVP.
- Caller-provided MCP context is only a hint; trusted corpus eligibility is
  derived server-side.
- First/last version lineage must be evidence-backed. Unknown lineage remains
  unknown.
- GitHub Actions use ephemeral databases and validation-only ingestion until
  export/import, encryption, retention, restore checks, and index promotion are
  explicitly implemented.

## What The Safety Rules Mean Operationally

The safety rules are implementation requirements, not documentation warnings.
Build them into boundaries, tests, database constraints where useful, and log
filters.

- Raw source text may exist only as a short-lived in-memory extractor candidate
  before redaction and classification. It must not be written to database
  columns, files, caches, logs, test snapshots, telemetry, embeddings, reranker
  inputs, CLI output, MCP output, or diagnostics.
- Redaction happens before chunking. Chunk boundaries, hashes, embeddings,
  tests, and citations must be based on sanitized text, not on raw text.
- Persistence paths should reject unredacted candidates. Do not rely on caller
  discipline when a guard function, type, status field, or validation check can
  enforce the rule.
- Corpus eligibility filters run before retrieval subqueries. Do not retrieve a broad set
  and filter it later, because ranking scores, counts, diagnostics, latency, and
  error messages can leak that ineligible material exists.
- MCP `caller_context_hint` can help disambiguate wording, but it never grants
  retrieval eligibility. Source allowlists, visibility labels, sensitivity
  policy, redaction status, license policy, and version scope are derived by the
  server.
- Diagnostics must be useful but safe. They can show sanitized IDs, score
  components, selected index path, filter summaries, redaction status,
  correlation IDs, and timings. They must not show SQL with sensitive literals,
  raw chunks, raw provider payloads, embedding vectors, pre-filter diagnostics,
  or ineligible result counts.
- Citations are mandatory for returned evidence. If the system cannot prove the
  source, it should drop the candidate, mark it as diagnostic-only, or report
  unknown lineage. Do not invent first/last versions.
- CI must not depend on paid model APIs, private services, durable databases, or
  live ingestion of sensitive repositories. Use deterministic local or mock
  embedding and reranking paths.

## Local And CI Prerequisites

The early phase steps create and verify most of this tooling. Before
implementing later steps, expect these local prerequisites to exist:

- Python 3.14.
- `uv` for dependency and lockfile management.
- `mise` for project tasks, tool versions, and common workflows.
- `git` for repository source acquisition and normal commits.
- `docker compose` for local PostgreSQL.
- PostgreSQL 18 with the `vector`, `pg_search`, and `pg_trgm` extensions.
- The repository's configured `mise` tasks for install, lint, type check, tests,
  database migration, and CI-equivalent checks.

CI expectations:

- GitHub Actions runs with ephemeral databases.
- CI uses validation-only ingestion until backup, restore, retention,
  encryption, and index promotion are explicitly implemented.
- CI must pass without external embedding, reranking, security scanning, or
  document conversion services unless a step explicitly adds a local,
  deterministic fallback.
- Tests that need source content should use fixtures that are safe to store in
  the repository. Fixture secrets must be fake values designed to test
  redaction.

Optional tools such as Docling, Tika, Unstructured, Gitleaks, detect-secrets,
Presidio, ScanCode, ORT, Semgrep, and language-native extractors are introduced
only where configured by a step. When adding optional adapters, keep the default
local and CI path deterministic.

## How To Execute The Plan

1. Start at Phase 1, Step 1 unless the user explicitly assigns a later step and
   the prerequisites are already satisfied.
2. Before editing product code for a step, read this README, `ARCHITECTURE.md`,
   and the current step file.
3. Confirm every prerequisite in the step file. Prerequisites are hard gates,
   not background reading suggestions.
4. Check the working tree for files you will touch. Other people or agents may
   be editing the repository. Work with their changes and do not revert
   unrelated edits.
5. Modify only the files required by the current step unless the step's
   implementation instructions clearly require another file.
6. Keep the change focused. Do not combine multiple MVP steps into one commit.
7. Run every command listed in `Tests And Checks`. Also run broader checks when
   the step tells you to, or when your change touches shared behavior.
8. Verify every acceptance criterion in the step file.
9. Commit once for the completed step, using the suggested commit message or a
   close equivalent that accurately describes the change.
10. Move to the next step only after the current step is complete.

If a step appears wrong or conflicts with `ARCHITECTURE.md`, stop and surface
the conflict. Do not silently re-architect the system inside an implementation
step.

## How To Use Each Step File

Every step file is an implementation contract. Read it from top to bottom before
making changes.

- `Goal`: the user-visible outcome of the step. Use this to understand why the
  step exists.
- `Prerequisites`: what must already be true. If a prerequisite is not met, do
  the earlier step first or report the blocker.
- `Files To Create Or Modify`: the expected edit boundary. Treat this as the
  default ownership list for the step.
- `Implementation Instructions`: the required build sequence and behavioral
  details. Follow the list directly unless the current codebase forces a small
  adaptation.
- `Tests And Checks`: the minimum verification work. Run all listed commands.
- `Acceptance Criteria`: the definition of done. Passing tests is not enough if
  an acceptance criterion is still unmet.
- `Suggested Commit Message`: the intended commit scope. Use it to keep history
  readable.

When implementing a step, copy no raw production source content into tests,
snapshots, comments, or logs. Use small fixtures and fake secret values. If a
new test needs sensitive-looking data, make it synthetic and confirm the exact
raw fixture value does not appear in persisted output.

## What Each Phase Does

Phase 1 establishes the project shell: Python package, task runner, lint/type
test tooling, local PostgreSQL, settings, migrations, extension checks, and
basic CI. After this phase, the repository should be installable, testable, and
able to start its required local database.

Phase 2 defines configuration and the core relational model. It creates the
source catalog shape, corpus eligibility records, redaction and license records,
index version records, embedding job records, database tasks, and migration
tests. After this phase, later code has stable data contracts to build on.

Phase 3 builds ingestion and sanitized storage. It lists configured sources,
records ingestion runs, reads local directories and Git repositories, discovers
artifacts, extracts content, redacts before persistence, chunks with structure
awareness, handles incremental changes and tombstones, and proves ingestion
safety in tests.

Phase 4 builds retrieval. It adds embedding providers, vector storage, BM25 and
pgvector indexes, exact lookup, lexical and semantic candidate retrieval, query
profiles, pre-subquery corpus eligibility filtering, rank fusion, reranking, evidence bundle
contracts, and retrieval tests. After this phase, retrieval should be safe and
evidence-backed inside the service layer.

Phase 5 exposes and operates the system. It adds ingest and retrieval CLI
commands, a read-only MCP stdio server, MCP `search`, `fetch`,
`explain_search`, and `list_sources`, evaluation commands and metrics, CI gates,
OpenTelemetry spans, Prometheus metrics, and GitHub Actions evaluation. After
this phase, the MVP should be usable locally and validated in CI.

## What Not To Do

- Do not add answer generation to the MVP.
- Do not add production HA, remote model serving, or embedding fine-tuning to
  the MVP.
- Do not create a hardcoded catalog of platform tools, products, CLIs, SDKs, or
  repositories in product code.
- Do not bypass configuration just because a single source works locally.
- Do not store raw source files, raw chunks, raw extracted text, raw secrets,
  raw provider payloads, or reversible secret hashes.
- Do not embed or rerank unredacted text.
- Do not trust MCP caller-provided context as retrieval eligibility.
- Do not run corpus eligibility filters only after retrieval has already produced candidate
  sets.
- Do not return uncited evidence.
- Do not hide source conflicts by merging them into one unsupported statement.
- Do not make MCP tools mutate ingestion state, configuration, databases, or
  external systems.
- Do not skip the deterministic local/mock path needed for CI.
- Do not broaden a step into adjacent steps just because nearby code is visible.

## Phase 1: Skeleton And Local Runtime

This phase creates the local development foundation and CI baseline. It should
not introduce ingestion, retrieval, model calls, or database-backed product
behavior before the listed steps add those capabilities.

- [Phase directory](01-skeleton-and-local-runtime/)
- [1.1 Python Project Scaffold](01-skeleton-and-local-runtime/01-python-project-scaffold.md)
- [1.2 Mise Task Runner](01-skeleton-and-local-runtime/02-mise-task-runner.md)
- [1.3 Lint Type Test Tooling](01-skeleton-and-local-runtime/03-lint-type-test-tooling.md)
- [1.4 Docker Compose Postgres](01-skeleton-and-local-runtime/04-docker-compose-postgres.md)
- [1.5 Pydantic Settings And Env Example](01-skeleton-and-local-runtime/05-pydantic-settings-and-env-example.md)
- [1.6 Alembic Base And Extension Migration](01-skeleton-and-local-runtime/06-alembic-base-and-extension-migration.md)
- [1.7 Extension Smoke Test](01-skeleton-and-local-runtime/07-extension-smoke-test.md)
- [1.8 GitHub Actions CI](01-skeleton-and-local-runtime/08-github-actions-ci.md)

## Phase 2: Configuration And Core Data Model

This phase gives the project stable configuration and database contracts. It is
where source identity, visibility, corpus eligibility, redaction, license, indexing, and
embedding job records become explicit instead of being implied by code.

- [Phase directory](02-configuration-and-data-model/)
- [2.1 Config Loader Models](02-configuration-and-data-model/01-config-loader-models.md)
- [2.2 Example Config Files](02-configuration-and-data-model/02-example-config-files.md)
- [2.3 Core SQLAlchemy Models](02-configuration-and-data-model/03-core-sqlalchemy-models.md)
- [2.4 Corpus Eligibility Policy Models](02-configuration-and-data-model/04-corpus-eligibility-policy-models.md)
- [2.5 Redaction And License Models](02-configuration-and-data-model/05-redaction-and-license-models.md)
- [2.6 Index Versions And Embedding Jobs](02-configuration-and-data-model/06-index-versions-and-embedding-jobs.md)
- [2.7 DB Mise Tasks](02-configuration-and-data-model/07-db-mise-tasks.md)
- [2.8 Model And Migration Tests](02-configuration-and-data-model/08-model-and-migration-tests.md)

## Phase 3: Generic Ingestion And Sanitized Storage

This phase turns configured sources into safe stored evidence. The key rule is
that extraction is not enough: content must be redacted, classified, cited, and
chunked safely before persistence or indexing.

- [Phase directory](03-ingestion-and-sanitized-storage/)
- [3.1 Sources List Command](03-ingestion-and-sanitized-storage/01-sources-list-command.md)
- [3.2 Ingestion Run Recording](03-ingestion-and-sanitized-storage/02-ingestion-run-recording.md)
- [3.3 Local Directory Ingestion](03-ingestion-and-sanitized-storage/03-local-directory-ingestion.md)
- [3.4 Git Repository Fetcher](03-ingestion-and-sanitized-storage/04-git-repository-fetcher.md)
- [3.5 Artifact Discovery](03-ingestion-and-sanitized-storage/05-artifact-discovery.md)
- [3.6 Extractor Interfaces And Basic Extractors](03-ingestion-and-sanitized-storage/06-extractor-interfaces-and-basic-extractors.md)
- [3.7 Redaction Before Persistence](03-ingestion-and-sanitized-storage/07-redaction-before-persistence.md)
- [3.8 Structure Aware Chunking](03-ingestion-and-sanitized-storage/08-structure-aware-chunking.md)
- [3.9 Incremental Ingestion And Tombstones](03-ingestion-and-sanitized-storage/09-incremental-ingestion-and-tombstones.md)
- [3.10 Ingestion Test Suite](03-ingestion-and-sanitized-storage/10-ingestion-test-suite.md)

## Phase 4: Embeddings, BM25, pgvector, And Retrieval

This phase builds the retrieval engine over sanitized records. Exact lookup,
BM25, and vector search are separate candidate paths that are filtered for corpus eligibility
before execution, then fused, optionally reranked, and returned as citation
backed evidence bundles.

- [Phase directory](04-embeddings-bm25-pgvector-retrieval/)
- [4.1 Embedding Provider Interface](04-embeddings-bm25-pgvector-retrieval/01-embedding-provider-interface.md)
- [4.2 Embedding Jobs And Vector Storage](04-embeddings-bm25-pgvector-retrieval/02-embedding-jobs-and-vector-storage.md)
- [4.3 ParadeDB BM25 Migration](04-embeddings-bm25-pgvector-retrieval/03-paradedb-bm25-migration.md)
- [4.4 pgvector HNSW Migration](04-embeddings-bm25-pgvector-retrieval/04-pgvector-hnsw-migration.md)
- [4.5 Exact Lookup Retrieval](04-embeddings-bm25-pgvector-retrieval/05-exact-lookup-retrieval.md)
- [4.6 BM25 Candidate Retrieval](04-embeddings-bm25-pgvector-retrieval/06-bm25-candidate-retrieval.md)
- [4.7 Vector Candidate Retrieval](04-embeddings-bm25-pgvector-retrieval/07-vector-candidate-retrieval.md)
- [4.8 Query Profiles](04-embeddings-bm25-pgvector-retrieval/08-query-profiles.md)
- [4.9 Corpus Eligibility Filtering Before Subqueries](04-embeddings-bm25-pgvector-retrieval/09-corpus-eligibility-filtering-before-subqueries.md)
- [4.10 Reciprocal Rank Fusion](04-embeddings-bm25-pgvector-retrieval/10-reciprocal-rank-fusion.md)
- [4.11 Reranker Interface](04-embeddings-bm25-pgvector-retrieval/11-reranker-interface.md)
- [4.12 Evidence Bundle Contract](04-embeddings-bm25-pgvector-retrieval/12-evidence-bundle-contract.md)
- [4.13 Retrieval Test Suite](04-embeddings-bm25-pgvector-retrieval/13-retrieval-test-suite.md)

## Phase 5: CLI, MCP, Evaluation, And Operations

This phase exposes the MVP to operators and agents. The CLI and MCP tools must
share the same retrieval service and safety checks; MCP remains read-only.
Evaluation and telemetry prove the retrieval path works and stays observable.

- [Phase directory](05-cli-mcp-evaluation-operations/)
- [5.1 Ingest CLI Commands](05-cli-mcp-evaluation-operations/01-ingest-cli-commands.md)
- [5.2 Retrieve Query Command](05-cli-mcp-evaluation-operations/02-retrieve-query-command.md)
- [5.3 Retrieve Explain Command](05-cli-mcp-evaluation-operations/03-retrieve-explain-command.md)
- [5.4 MCP Stdio Server](05-cli-mcp-evaluation-operations/04-mcp-stdio-server.md)
- [5.5 MCP Search Tool](05-cli-mcp-evaluation-operations/05-mcp-search-tool.md)
- [5.6 MCP Fetch Tool](05-cli-mcp-evaluation-operations/06-mcp-fetch-tool.md)
- [5.7 MCP Explain And List Sources](05-cli-mcp-evaluation-operations/07-mcp-explain-and-list-sources.md)
- [5.8 Eval Run Command](05-cli-mcp-evaluation-operations/08-eval-run-command.md)
- [5.9 Evaluation Metrics](05-cli-mcp-evaluation-operations/09-evaluation-metrics.md)
- [5.10 Evaluation Thresholds And CI Gates](05-cli-mcp-evaluation-operations/10-evaluation-thresholds-and-ci-gates.md)
- [5.11 OpenTelemetry Spans](05-cli-mcp-evaluation-operations/11-opentelemetry-spans.md)
- [5.12 Prometheus Metrics](05-cli-mcp-evaluation-operations/12-prometheus-metrics.md)
- [5.13 GitHub Actions Eval](05-cli-mcp-evaluation-operations/13-github-actions-eval.md)
