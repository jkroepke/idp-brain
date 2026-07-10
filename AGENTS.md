# idp-brain repository guidance

These rules apply to every Codex task in this repository.

- This is a Python 3.14 project.
- Use `uv` for dependencies and `uv.lock`.
- Use `mise` as the documented command surface.
- Prefer `mise run <task>` over invoking internal tools directly.
- Follow `ARCHITECTURE.md` and the relevant file under `plans/`.
- Inspect existing code before proposing or writing replacements.
- Preserve unrelated changes. Never reset, clean, overwrite, or discard work
  whose ownership is unclear.
- Never persist, embed, log, or return raw unsanitized source content.
- Do not weaken validation, error handling, security, or acceptance criteria to
  reduce code size.

## Opt-in coding flow

The multi-agent implementation workflow is available as `$coding`.

Do not activate, imitate, or partially execute it unless the user explicitly
invokes `$coding`.

Without `$coding`, handle questions, architecture discussions, repository
analysis, documentation, and explicitly requested changes normally. Do not
automatically create subagents, branches, commits, or pull requests.
