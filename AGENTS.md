# idp-brain repository guidance

This file contains only repository-wide rules that apply to every Codex task.

## Repository conventions

This is a Python 3.14 project.

- Use `uv` for dependencies and `uv.lock`.
- Use `mise` as the documented command surface.
- Prefer `mise run <task>` over invoking internal tools directly.
- Follow `ARCHITECTURE.md` and the relevant files under `plans/`.
- Preserve unrelated existing changes.
- Do not reset, clean, overwrite, or discard work whose ownership is unclear.
- Never persist, embed, log, or return raw unsanitized source content.

## Optional coding workflow

The complete multi-agent implementation workflow is available through the
`$coding-flow` skill.

Do not activate, imitate, or partially execute that workflow unless the user
explicitly invokes `$coding-flow`.

Without `$coding-flow`, handle questions, architecture discussions, repository
analysis, documentation, and explicitly requested small changes normally.
Do not automatically create branches, commits, pull requests, or subagents.
