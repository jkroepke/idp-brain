---
name: coding
description: Run the explicit, token-efficient multi-agent code-development workflow for idp-brain.
---

# Coding flow

This workflow is active only because the user invoked `$coding`.

## Select the lowest safe mode

The first argument may be `lean`, `standard`, or `high-risk`.

When it is omitted, select the lowest safe mode and state the selection in one
line. Do not ask only to confirm the mode.

### Lean

Use for documentation, comments, mechanical configuration, formatting,
trivial single-file changes, and well-understood low-blast-radius code.

```text
implementer -> root validation
```

### Standard

Use for normal product code where an independent correctness check is useful.

```text
implementer -> reviewer -> root validation
```

### High-risk

Use when a defect could leak data, corrupt state, silently produce wrong
evidence, or be difficult to recover from. Examples include migrations,
transactions, retries, concurrency, redaction, corpus eligibility, MCP
boundaries, destructive operations, and retrieval ranking or lineage.

```text
implementer -> deep_reviewer -> root validation
```

Do not run both `reviewer` and `deep_reviewer` for the same revision.

## Token-efficiency rules

- Never spawn the full agent set.
- Keep at most one write-capable agent active.
- Spawn `explorer` only when the affected execution path is not already clear.
- Spawn `verifier` only when validation is substantial or logs need isolated
  analysis.
- Reuse the same implementer for findings, validation failures, and related CI
  failures.
- Reuse the same reviewer for re-review.
- Agents read repository files themselves. Pass paths and a bounded work
  package instead of copied documents or prior transcripts.
- Do not ask multiple agents to perform the same exploration or full test run.
- Use scripts and deterministic checks once instead of repeating model work.
- Complete one work package before opening another.
- Parallel implementation is allowed only for truly disjoint directories with
  explicit integration contracts. Sequential work is the default.

## Sources of truth

Use this precedence:

1. The user's current instruction.
2. `ARCHITECTURE.md`.
3. The active plan step under `plans/`.
4. Current code and tests.

Inspect current code before assuming planned work is absent. Surface genuine
conflicts rather than silently changing requirements.

## Unit of work

One plan step file is the default unit. Split it only into independently
testable acceptance slices with bounded files, explicit acceptance criteria,
independent validation, and clear integration points.

Use one branch and one pull request per unit by default.

## Compact handoff

Pass only:

```text
Goal:
Non-goals:
Plan or issue:
Relevant paths:
Acceptance criteria:
Validation:
Risk focus:
Base or diff:
```

Do not pass full conversations or complete copies of repository documents.

## Root ownership

The root owns work-package selection, flow-mode selection, branch creation,
agent lifecycle, final validation, staging, commits, pushes, pull requests,
GitHub Actions monitoring, and merge.

The root does not implement production changes or perform the independent
review.

## Execution

1. Inspect the working tree, current plan, architecture, and existing code.
2. Select one work package and the lowest safe mode.
3. Create the feature branch.
4. Use `explorer` only when targeted code-path evidence is missing.
5. Send one compact work package to `implementer`.
6. The implementer changes code and tests, runs relevant checks, and reports
   changed files, command outcomes, failures, and residual risks.
7. For `lean`, proceed to root validation.
8. For `standard`, give `reviewer` the work package, actual diff, and validation
   summary.
9. For `high-risk`, give `deep_reviewer` those inputs plus only the relevant
   checklist from `references/`.
10. Forward findings to the same implementer.
11. Give the same reviewer only the updated diff and resolution summary.
12. Use `verifier` only if substantial independent validation is still justified.
13. Root runs final repository-level validation once.
14. Root stages intended files, commits, pushes, creates or updates the draft
    pull request, and monitors required checks.
15. Route related CI failures to the same implementer and re-review code changes.
16. Mark ready and merge only after every gate passes.

## Ponytail

Do not copy Ponytail's full instructions into subagent prompts.

Keep always-on Ponytail disabled for token-sensitive work. Invoke
`$ponytail-review` only for a concrete over-engineering signal, such as a new
dependency, a one-implementation abstraction, unexpected files, future
scaffolding, or a diff much larger than the acceptance criteria require.

Ponytail review supplements minimalism. It never replaces correctness or
security review.

## Git boundaries

Subagents must not create or switch branches, stage, commit, push, or create,
approve, update, or merge pull requests.

## Merge gates

Merge only when acceptance criteria are satisfied, required review returned
exactly `APPROVED`, final validation and required checks pass, no blocker or
merge conflict remains, and unrelated work was preserved.

## Stop conditions

Stop only for completion, a genuine requirement or architecture conflict,
missing information that cannot be derived, or unsafe validation/integration.
