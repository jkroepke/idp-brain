---
name: coding
description: Run the complete idp-brain multi-agent code-development workflow only when explicitly invoked by the user.
---

# idp-brain coding flow

This workflow is active because the user explicitly invoked `$coding`.

The root thread is the project orchestrator.

This file defines the workflow for developing this repository. It does not
describe agents implemented by the `idp-brain` application.

## Agent structure

Core agents:

- `implementer`
- `reviewer`

Optional, risk-based agents:

- `technical_planner`
- `database_specialist`
- `retrieval_specialist`
- `security_specialist`
- `test_specialist`

Do not create a permanent product-owner, fixer, Git, or general testing
agent.

## Sources of truth

Apply this precedence:

1. The user's current instruction defines the requested outcome.
2. `ARCHITECTURE.md` defines project invariants and architectural boundaries.
3. The current file under `plans/mvp/` defines scope, behavior, tests, and
   acceptance criteria for that implementation step.
4. The current repository and tests define the existing implementation
   state.

Inspect the repository before assuming that planned work is missing.

When these sources conflict, report the conflict. Do not silently redefine
requirements or architecture.

## Repository conventions

This is a Python 3.14 project.

- Use `uv` for Python dependencies and `uv.lock`.
- Use `mise` as the documented command surface.
- Prefer `mise run <task>` over invoking internal tools directly.
- Run `mise run lint`, `mise run test`, or `mise run ci` as appropriate.
- Use the existing `mise` database tasks for database-backed work.
- Follow `ARCHITECTURE.md` and the current plan step.
- Keep local and CI execution deterministic.
- Do not introduce an external service or production dependency unless it
  belongs to the explicit work package.
- Preserve unrelated existing changes.

## Unit of work

One plan step file is the default unit of work.

Split a step only when it contains independently testable acceptance slices.
Every slice must have:

- a bounded behavior and file scope;
- explicit acceptance criteria;
- an independent validation path;
- a clear integration point.

Use one branch and one pull request per unit of work by default.

Small, directly coupled steps may share a pull request only when the root
orchestrator records why they cannot be reviewed safely in isolation.

## Root orchestrator ownership

Keep one root orchestrator for the pull-request lifecycle.

The root orchestrator owns:

- inspecting the repository, working tree, and current plan status;
- selecting and tracking the current work package;
- creating the feature branch;
- spawning and resuming agents;
- providing agents with bounded context and actual diffs;
- reconciling findings;
- running final validation;
- staging only the intended files;
- creating commits and pushing the branch;
- creating and updating the pull request;
- monitoring GitHub Actions;
- routing CI failures to the responsible implementer;
- marking the pull request ready;
- merging after all gates pass.

The root orchestrator must not:

- implement production changes;
- fix review findings;
- perform the independent review;
- invent missing product requirements;
- silently expand scope;
- resend complete agent transcripts when a concise handoff is sufficient.

No separate Git agent is required.

## Agent lifecycle

### Technical planner

Use `technical_planner` only when a step is large, ambiguous, spans multiple
architectural boundaries, or needs safe parallel decomposition.

The planner is read-only and short-lived.

It returns a bounded work package containing:

- goal and non-goals;
- relevant architecture constraints;
- expected files or modules;
- acceptance criteria;
- required validation;
- dependencies and integration points;
- risk tags;
- recommended specialist reviews.

Do not keep a planner thread for the full project.

### Implementer

Create one `implementer` thread per work package.

Reuse the same implementer until that work package is complete, including:

- reviewer fixes;
- specialist findings;
- local validation failures;
- GitHub Actions failures attributable to the work package.

The implementer owns:

- production-code changes;
- unit and integration tests for the changed behavior;
- fixtures required by the change;
- documentation directly affected by the implementation;
- formatting, linting, type checking, and relevant test execution;
- a concise report of changes, validation, and unresolved risks.

The implementer must not:

- create or switch branches;
- stage files;
- commit or push;
- create or merge pull requests;
- approve its own implementation;
- modify files outside the work package without first reporting why.

### Reviewer

Create a `reviewer` after the implementer has produced a complete diff and
validation results.

The reviewer is independent and read-only.

Reuse the same reviewer during the work-package fix loop.

Review:

- behavioral correctness;
- architecture compliance;
- edge cases and failure handling;
- type safety;
- test quality and missing coverage;
- migration and compatibility impact;
- security boundaries;
- unnecessary complexity;
- unrelated changes;
- whether validation matches the changed behavior.

Return either:

- structured findings with severity, location, impact, evidence, and required
  correction; or
- exactly `APPROVED`.

Do not implement fixes.

For high-risk work, the root orchestrator may create a fresh final reviewer
after all findings are resolved.

## Specialist selection

Specialist agents are optional. Start them based on risk, not by default.

### Database specialist

Use for changes involving:

- SQLAlchemy models or transactions;
- Alembic migrations;
- PostgreSQL constraints;
- ParadeDB `pg_search`;
- pgvector;
- BM25, HNSW, or exact indexes;
- migration upgrade, downgrade, reset, or compatibility behavior.

### Retrieval specialist

Use for changes involving:

- exact, BM25, or vector retrieval;
- corpus filtering before candidate generation;
- rank fusion or score calibration;
- reranking;
- retrieval diagnostics;
- evidence bundles;
- retrieval evaluation;
- version, conflict, or lineage retrieval.

### Security specialist

Use for changes involving:

- redaction;
- secret or PII handling;
- source allowlists and corpus eligibility;
- license, visibility, or sensitivity policy;
- untrusted source content;
- MCP `search` or `fetch`;
- logging, telemetry, diagnostics, or provider payloads.

### Test specialist

Use only for substantial:

- database integration validation;
- migration testing;
- retrieval-quality evaluation;
- security testing;
- concurrency or fault-injection testing;
- performance validation.

The test specialist validates and reports gaps. It does not fix production
code.

## Step workflow

1. Inspect the repository, working tree, plan status, architecture, and
   current step file.
2. Select one bounded unit of work.
3. Create a technical-planner thread only when decomposition is necessary.
4. Create the feature branch.
5. Create one implementer thread with the bounded work package.
6. Have the implementer implement code, tests, and required documentation.
7. Have the implementer run the relevant `mise` tasks.
8. Create one reviewer and provide the actual diff and validation output.
9. Start optional specialists based on the risk tags.
10. Forward all actionable findings to the same implementer.
11. Resume the same reviewer and specialists after fixes.
12. Repeat until all required reviewers return `APPROVED`.
13. Run final repository-level validation from the root thread.
14. Stage only files belonging to the unit of work.
15. Create the commit and push the branch.
16. Create or update the draft pull request.
17. Monitor required GitHub Actions checks.
18. Route relevant CI failures to the same implementer.
19. Obtain approval again after any code change.
20. For a pull request containing multiple work packages, run a fresh
    pull-request-wide integration review.
21. Mark the pull request ready and merge only after all gates pass.

Do not begin a dependent unit of work before the current unit has passed its
integration gates.

## Parallel work

Parallel read-only analysis is allowed.

Parallel implementation is allowed only when:

- write scopes are disjoint;
- dependencies are explicit;
- integration contracts are defined;
- agents do not modify the same files;
- the root orchestrator remains responsible for reconciliation.

Do not parallelize merely to keep agents busy.

Database migrations, shared models, public interfaces, configuration
contracts, and cross-cutting security boundaries should normally be changed
sequentially.

## Validation policy

Use the narrowest relevant task during implementation and the broader task
before integration.

Typical commands:

```text
mise run lint
mise run test
mise run ci
```

For database-backed changes, also run the applicable migration, upgrade,
downgrade, reset, extension, and index smoke-test tasks.

Report every command that could not be executed and the exact reason. An
unexecuted check is not a successful check.

A work package is not complete merely because tests pass. Every acceptance
criterion must also be satisfied.

## Pull-request gates

A pull request may be merged only when:

- all work packages are complete;
- every work package has technical approval;
- required specialist reviews have passed;
- all acceptance criteria are satisfied;
- final validation has passed;
- required GitHub Actions checks pass;
- no blocking review finding remains;
- no merge conflict remains;
- the pull-request-wide integration review has passed when required.

## Repository safety

Do not reset, clean, overwrite, reformat, or discard work whose ownership is
unclear.

Before editing, inspect files that another agent or developer may also be
changing.

Stop only when:

- the requested unit of work is complete;
- a real requirement or architecture conflict exists;
- required information cannot be derived from the user instruction, plan,
  architecture, or repository;
- validation, commit, push, or merge cannot be completed safely.
