# idp-brain

`idp-brain` is a local-first, source-backed retrieval pipeline. The current
implementation is intentionally small: a Python package scaffold, a read-only
CLI shell, and project task wiring.

## Local Development

Use `mise` as the project command surface. Runtime dependencies are tracked in
`mise.toml`:

- Python `3.14.6`
- `uv` for Python dependency and lockfile management

Install the tracked tools and project dependencies:

```sh
mise install
mise run install
```

Run the checks available after the initial scaffold:

```sh
mise run lint
mise run test
mise run ci
```

Run the local PostgreSQL runtime and migrations when working on database-backed
steps:

```text
mise run up
mise run down
mise run db:migrate
```

The following task names are reserved now and intentionally fail until their
own MVP steps implement them:

```text
mise run db:reset
mise run ingest
mise run retrieve -- <query>
mise run eval
```

Implementation steps live under `plans/mvp/`. Start with
`plans/mvp/README.md`, then complete the step files in order.
