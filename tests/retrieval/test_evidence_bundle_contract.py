from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import column, table

from idp_brain.retrieval.corpus_filters import TrustedCorpusScope
from idp_brain.retrieval.evidence import (
    CitationDTO,
    ConflictMarker,
    EvidenceAssembler,
    SQLAlchemyEvidenceFetcher,
    TrustedEvidenceRecord,
)
from idp_brain.retrieval.models import Candidate, FusedCandidate, RetrievalFilters


def candidate(chunk_id: str = "chunk:1", relationship: bool = False) -> FusedCandidate:
    diagnostics = {}
    path = "bm25"
    if relationship:
        path = "relationship"
        diagnostics = {
            "relationship_path": [
                {
                    "relationship_type": "references",
                    "direction": "outbound",
                    "depth": 1,
                    "from_id": "chunk:seed",
                    "to_id": chunk_id,
                    "citation_ids": ["citation:1"],
                }
            ]
        }
    item = Candidate(
        chunk_id=chunk_id,
        retrieval_path=path,
        rank=1,
        matched_fields=(),
        metadata={},
        diagnostics=diagnostics,
    )
    return FusedCandidate(
        chunk_id=chunk_id, fused_score=1, path_candidates={path: item}
    )


class Fetcher:
    def __init__(self, *, trusted: bool = True, citation: bool = True) -> None:
        self.trusted = trusted
        self.citation = citation

    def fetch(self, candidate_ids, filters, query_profile_id):
        ids = ("citation:1",) if self.citation else ()
        records = {
            candidate_id: TrustedEvidenceRecord(
                item_id=candidate_id,
                sanitized_text="safe [REDACTED:SECRET:1] " + "x" * 50,
                sanitized_content_hash="sha256:safe",
                citation_ids=ids,
                redaction_status="redacted",
                source_id="source:1",
                source_version_id="version:1",
                corpus_eligibility_label="eligible",
                authority_rank=1,
            )
            for candidate_id in candidate_ids
        }
        if not self.trusted:
            records = {}
        citations = {
            "citation:1": CitationDTO(
                citation_id="citation:1",
                source_id="source:1",
                source_version_id="version:1",
                item_id="chunk:1",
                source_url="https://example.invalid/source",
                source_type="documentation_file",
                locator="docs/safe.md",
                sanitized_content_hash="sha256:safe",
                redaction_status="redacted",
                visibility_label="invited_users",
                corpus_eligibility_label="eligible",
            )
        }
        conflicts = [
            ConflictMarker(
                conflict_id="conflict:1",
                status="unresolved",
                competing_item_ids=("chunk:1", "chunk:2"),
                competing_citation_ids=("citation:1", "citation:2"),
            )
        ]
        return records, citations, conflicts


def assemble(fetcher: Fetcher, candidates=None, budget: int = 8):
    return EvidenceAssembler(fetcher).assemble(
        query="find password=hunter2",
        normalized_query_intent={"symbols": ()},
        candidates=candidates or [candidate()],
        query_profile_id="docs_qa",
        active_index_version_id="index:1",
        token_budget=budget,
        filters_applied=("visibility", "license_policy_status"),
        filters=RetrievalFilters(),
    )


def test_bundle_is_sanitized_citation_and_hash_backed_and_budgeted() -> None:
    bundle = assemble(Fetcher())
    assert bundle.query == "find [redacted]"
    assert bundle.evidence_items[0].citation_ids == ("citation:1",)
    assert bundle.evidence_items[0].sanitized_content_hash == "sha256:safe"
    assert len(bundle.evidence_items[0].sanitized_excerpt) <= 32
    assert bundle.token_budget.truncated_item_count == 1
    assert "hunter2" not in bundle.model_dump_json()


def test_untrusted_or_uncited_candidates_are_dropped_with_counts_only() -> None:
    for fetcher in (Fetcher(trusted=False), Fetcher(citation=False)):
        bundle = assemble(fetcher)
        assert bundle.evidence_items == ()
        assert bundle.diagnostics.dropped_missing_evidence_count == 1


def test_relationship_metadata_is_typed_bounded_and_citation_backed() -> None:
    bundle = assemble(Fetcher(), [candidate(relationship=True)])
    path = bundle.evidence_items[0].relationship_path[0]
    assert path.relationship_type == "references"
    assert path.citation_ids == ("citation:1",)


@pytest.mark.parametrize(
    "path",
    [
        "not-a-sequence",
        [{}],
        [
            {
                "relationship_type": "references",
                "direction": "outbound",
                "depth": 1,
                "from_id": "seed",
                "to_id": "middle",
                "citation_ids": ["citation:1"],
            },
            {
                "relationship_type": "references",
                "direction": "outbound",
                "depth": 2,
                "from_id": "wrong",
                "to_id": "chunk:1",
                "citation_ids": ["citation:1"],
            },
        ],
        [
            {
                "relationship_type": "references",
                "direction": "outbound",
                "depth": 1,
                "from_id": "chunk:1",
                "to_id": "chunk:1",
                "citation_ids": ["citation:1"],
            }
        ],
        [
            {
                "relationship_type": "references",
                "direction": "outbound",
                "depth": 1,
                "from_id": "seed",
                "to_id": "wrong-endpoint",
                "citation_ids": ["citation:1"],
            }
        ],
    ],
)
def test_malformed_relationship_paths_are_controlled_drops(path: object) -> None:
    fused = candidate(relationship=True)
    relationship = fused.path_candidates["relationship"].model_copy(
        update={"diagnostics": {"relationship_path": path}}
    )
    fused = fused.model_copy(update={"path_candidates": {"relationship": relationship}})
    bundle = assemble(Fetcher(), [fused])
    assert bundle.evidence_items == ()
    assert bundle.diagnostics.dropped_missing_evidence_count == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"source_url": "https://user:secret@example.invalid/source"},
        {"source_url": "https://example.invalid/source?token=secret"},
        {"source_url": "file:///tmp/source"},
        {"locator": r"C:\\private\\source.txt"},
        {"locator": "/private/source.txt"},
        {"commit_sha": "password=secret"},
    ],
)
def test_unsafe_citation_provenance_is_rejected(updates: dict[str, str]) -> None:
    citation = Fetcher().fetch(("chunk:1",), RetrievalFilters(), "docs_qa")[1][
        "citation:1"
    ]
    payload = citation.model_dump()
    payload.update(updates)
    with pytest.raises(ValidationError):
        CitationDTO.model_validate(payload)


class ConflictSession:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return self

    def mappings(self):
        return self.rows


def _citation(citation_id: str, item_id: str) -> CitationDTO:
    return CitationDTO(
        citation_id=citation_id,
        source_id="source:1",
        source_version_id="version:1",
        item_id=item_id,
        source_url="https://example.invalid/source",
        source_type="documentation_file",
        locator="docs/safe.md",
        sanitized_content_hash="sha256:safe",
        redaction_status="redacted",
        visibility_label="invited_users",
        corpus_eligibility_label="eligible",
    )


def test_conflicts_are_scoped_to_selected_evidence_before_completeness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = table("filtered_claims", column("id"), column("primary_citation_id"))
    monkeypatch.setattr(
        "idp_brain.retrieval.evidence.build_filtered_claim_scope",
        lambda *args: claims,
    )
    session = ConflictSession(
        [
            {
                "id": "selected-conflict",
                "status": "unresolved",
                "left_citation_id": "citation:1",
                "right_citation_id": "citation:2",
            }
        ]
    )
    fetcher = SQLAlchemyEvidenceFetcher(session, trusted_scope=TrustedCorpusScope())  # type: ignore[arg-type]
    citations = {
        "citation:1": _citation("citation:1", "chunk:1"),
        "citation:2": _citation("citation:2", "chunk:2"),
    }
    result = fetcher._conflicts(
        object(), RetrievalFilters(), citations, "conflict_search"
    )
    assert result[0].conflict_id == "selected-conflict"
    sql = str(session.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "primary_citation_id IN ('citation:1', 'citation:2')" in sql


def test_selected_conflict_with_missing_competing_evidence_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = table("filtered_claims", column("id"), column("primary_citation_id"))
    monkeypatch.setattr(
        "idp_brain.retrieval.evidence.build_filtered_claim_scope",
        lambda *args: claims,
    )
    session = ConflictSession(
        [
            {
                "id": "selected-conflict",
                "status": "unresolved",
                "left_citation_id": "citation:1",
                "right_citation_id": "missing",
            }
        ]
    )
    fetcher = SQLAlchemyEvidenceFetcher(session, trusted_scope=TrustedCorpusScope())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="incomplete"):
        fetcher._conflicts(
            object(),
            RetrievalFilters(),
            {"citation:1": _citation("citation:1", "chunk:1")},
            "conflict_search",
        )
