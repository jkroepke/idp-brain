# 3.4: Git Repository Fetcher

## Goal
Implement `git_repository` fetching with local cache isolation, commit and ref provenance, and a deterministic local fixture fallback that makes CI independent of remote Git services.

## Prerequisites
- `ARCHITECTURE.md` remains the source of truth for architecture decisions in this step.
- Phase 3.2 and Phase 3.3 are complete.
- The `git` CLI is available in local development and CI.
- Source configuration supports `git_repository` sources with repository URL, tracked refs, version strategy, include paths, exclude paths, extractor profile, source priority, access labels, sensitivity class, and license policy.

## Files To Create Or Modify
- `src/idp_brain/ingestion/fetchers/git_repository.py`
- `src/idp_brain/ingestion/git_client.py`
- `src/idp_brain/ingestion/version_map.py`
- `src/idp_brain/repositories/source_changes.py`
- `src/idp_brain/repositories/source_versions.py`
- `config/sources.yaml`
- `tests/fixtures/git_repository/README.md`
- `tests/fixtures/git_repository/schema.json`
- `tests/test_git_repository_fetcher.py`

## Implementation Instructions
1. Add a `GitRepositoryFetcher` selected for `source_type: git_repository`.
2. Clone or fetch into a local ingestion cache outside source control, such as `.cache/idp-brain/ingestion/git/<source_id>/`, and ensure `.gitignore` already excludes this cache.
3. Support local fixture repositories by accepting `file://` URLs and plain fixture paths in tests; all CI tests must use local repositories created from fixtures, not GitHub or another remote service.
4. For network URLs, use only the `git` CLI and configured credentials from the environment; do not require forge API access.
5. Resolve tracked branches, tags, and explicit commits to immutable commit SHAs before artifact discovery begins.
6. Record `source_versions` with source ID, commit SHA, branch or tag label, repository URL, fetch timestamp, fetch status, and access, visibility, sensitivity, and license policy labels.
7. Build an initial version map from tags, branches, commit ancestry, and file membership where the local repository proves the relationship. When first containing version or last containing version cannot be proven, store `unknown` or `NULL`; do not guess.
8. Record basic `source_changes` for commits reachable from the fetched refs: commit SHA, parent SHAs, author timestamp if safe, committer timestamp, sanitized commit subject, source ID, source version ID, access label, visibility label, sensitivity class, and license policy label. Until the Phase 3.7 redaction stage is available, sanitize commit subjects through the same diagnostic sanitizer used for run failures; do not persist raw commit subjects or full commit messages.
9. Treat remote forge enrichment as explicitly out of scope for this step unless credentials and a later source profile enable it; local Git data is sufficient for MVP fetch provenance.
10. On fetch failure, update the ingestion run with sanitized command, exit code, source ID, and retryable flag, but do not log tokens, credentials, raw file contents, or raw diffs.

## Tests And Checks
- `git --version`
- `mise run up`
- `mise run db:migrate`
- `uv run pytest tests/test_git_repository_fetcher.py`
- `mise run test`
- Passing condition: tests create or use a local fixture repository with fixed `user.name`, `user.email`, `GIT_AUTHOR_DATE`, and `GIT_COMMITTER_DATE`, fetch it through the same fetcher path as real Git sources, resolve refs to commit SHAs, record source versions and basic changes, and pass with network disabled.

## Acceptance Criteria
- `git_repository` sources fetch through a cache outside source control.
- Local `file://` or fixture-path repositories provide deterministic CI coverage.
- Source versions and changes are evidence-backed by local Git metadata.
- Unknown first/last containing versions remain unknown rather than inferred.
- No raw unsanitized chunks, raw diffs, credentials, tokens, raw commit subjects, or unredacted commit bodies are persisted, embedded, logged, or returned.

## Suggested Commit Message
`feat: add git repository fetcher`
