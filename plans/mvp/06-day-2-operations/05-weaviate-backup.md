# 6.5: Weaviate Backup And Restore

## Goal

Use Weaviate's supported backup API and prove restoration into an empty instance.

## Instructions

- configure the filesystem backup backend for local development
- add `mise run weaviate:backup`
- add `mise run weaviate:restore-smoke-test`
- use bounded backup identifiers without source or credential data
- restore into an empty disposable instance or collection generation
- run retrieval and citation checks after restore
- document production retention, encryption, replication, and recovery objectives as deployment policy

## Checks

- backup succeeds after fixture ingestion
- restore succeeds without the original data volume
- object counts, expected evidence IDs, and citation properties match
- restored retrieval and evaluation pass
- `mise run ci`

## Acceptance Criteria

The persistent Weaviate state can be backed up and restored independently from source rebuilds.
