# Codex project workflow

The root thread is the project orchestrator.

Use these custom agents:

- `product_owner`
- `coder`
- `reviewer`

The implementation plan under `plans/mvp/` is the source of truth.

## Repository workflow

This is a Python 3.14 project.

- Use `uv` for Python dependencies and `uv.lock`.
- Use `mise` as the documented command surface.
- Prefer `mise run <task>` over invoking internal tools directly.
- Run `mise run lint`, `mise run test`, or `mise run ci` as appropriate.
- For database-backed work, use the existing `mise` database tasks.
- Follow `ARCHITECTURE.md` and the relevant plan files.

## Unit of work

Treat one second-level plan item as one implementation step.

Process steps sequentially unless the plan explicitly permits parallel work.

## Agent lifecycle

Keep one `product_owner` thread for the project run.

For each implementation step:

- create one `coder` thread;
- create one `reviewer` thread;
- reuse both threads until the step is complete;
- do not create a separate fixer agent.

## Step workflow

1. Ask `product_owner` for the next incomplete step and a bounded work package.
2. Ask `coder` to implement and validate the work package without committing.
3. Ask `reviewer` to review the actual diff and validation results.
4. When review findings exist:
    - resume the same `coder`;
    - forward the findings;
    - resume the same `reviewer` after the fixes.
5. Repeat until the reviewer returns `APPROVED`.
6. Ask `product_owner` to validate the completed result.
7. When product findings exist:
    - resume the same `coder`;
    - obtain reviewer approval again;
    - obtain product acceptance again.
8. After technical approval and product acceptance, resume `coder`.
9. The coder creates one commit, pushes it, and reports the commit hash.
10. Continue automatically with the next incomplete step.

Do not start the next step before the current commit is pushed successfully.

## Orchestrator boundaries

The root orchestrator coordinates agents and tracks progress.

It must not:

- implement changes;
- fix findings;
- perform the independent review;
- commit or push;
- expand plan scope;
- resend full agent transcripts when a concise result is sufficient.

## Repository safety

Preserve unrelated existing changes.

Do not reset, clean, overwrite, or discard work whose ownership is unclear.

Stop only when:

- all plan steps are complete;
- the product owner reports a real blocker;
- required information cannot be derived from the plan or repository;
- validation, commit, or push cannot be completed safely.
