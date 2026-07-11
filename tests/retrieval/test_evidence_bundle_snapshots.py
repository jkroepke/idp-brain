from __future__ import annotations

import json

from test_evidence_bundle_contract import Fetcher, assemble


def test_evidence_bundle_json_snapshot_is_stable() -> None:
    payload = json.loads(assemble(Fetcher()).model_dump_json())
    assert payload["selected_chunk_ids"] == ["chunk:1"]
    assert payload["citations"][0]["citation_id"] == "citation:1"
    assert payload["diagnostics"] == {
        "query_profile_id": "docs_qa",
        "active_index_version_id": "index:1",
        "retrieval_paths": ["bm25"],
        "selected_candidate_count": 1,
        "dropped_missing_evidence_count": 0,
        "filters_applied": ["visibility", "license_policy_status"],
        "candidates": [
            {
                "item_id": "chunk:1",
                "fused_rank": None,
                "reranked_rank": None,
                "fused_score": 1.0,
                "rerank_score": None,
                "retrieval_paths": ["bm25"],
            }
        ],
    }
    assert "raw" not in json.dumps(payload, sort_keys=True)
