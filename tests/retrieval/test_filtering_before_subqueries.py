from __future__ import annotations

import pytest
from sqlalchemy import literal, select, union_all
from sqlalchemy.dialects import postgresql

from idp_brain.config.retrieval import RelationshipTraversalConfig
from idp_brain.retrieval.corpus_filters import build_bounded_relationship_traversal


def _edge_scope():
    rows = [
        ("r1", "references", "a", "b"),
        ("r2", "references", "a", "c"),
        ("r3", "references", "a", "d"),
        ("r4", "references", "b", "a"),
        ("r5", "contains", "b", "e"),
    ]
    selects = [
        select(
            literal(edge_id).label("id"),
            literal(edge_type).label("relationship_type"),
            literal("chunk").label("from_entity_type"),
            literal(source).label("from_entity_id"),
            literal("chunk").label("to_entity_type"),
            literal(target).label("to_entity_id"),
        )
        for edge_id, edge_type, source, target in rows
    ]
    return union_all(*selects).cte("filtered_relationships")


def _profile(**updates):
    values = {
        "enabled": True,
        "relationship_types": ["references"],
        "max_depth": 2,
        "max_fanout_per_seed": 2,
        "max_relationship_candidates": 3,
        "direction": "outbound",
        "cycle_handling": "skip_seen",
        "seed_sources": ["exact"],
    }
    values.update(updates)
    return RelationshipTraversalConfig(**values)


def test_relationship_traversal_sql_enforces_all_bounds_before_expansion() -> None:
    query = build_bounded_relationship_traversal(
        _edge_scope(), (("chunk", "a"),), _profile()
    )
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert "WITH RECURSIVE" in sql
    assert "typed_relationship_edges" in sql
    assert "row_number() OVER" in sql
    assert "fanout_rank" in sql
    assert "visited_ids" in sql
    assert "relationship_type IN" in sql
    assert "depth <" in sql
    assert "LIMIT" in sql


def test_direction_changes_oriented_endpoint_join() -> None:
    outbound = str(
        build_bounded_relationship_traversal(
            _edge_scope(), (("chunk", "a"),), _profile(direction="outbound")
        )
    )
    inbound = str(
        build_bounded_relationship_traversal(
            _edge_scope(), (("chunk", "a"),), _profile(direction="inbound")
        )
    )
    assert "from_entity_id AS from_id" in outbound
    assert "to_entity_id AS from_id" in inbound


def test_disabled_or_seedless_traversal_is_empty() -> None:
    disabled = RelationshipTraversalConfig()
    query = build_bounded_relationship_traversal(
        _edge_scope(), (("chunk", "a"),), disabled
    )
    assert "where" in str(query).lower()
    query = build_bounded_relationship_traversal(_edge_scope(), (), _profile())
    assert "where" in str(query).lower()


def test_candidate_limit_is_taken_from_profile() -> None:
    query = build_bounded_relationship_traversal(
        _edge_scope(), (("chunk", "a"),), _profile(max_relationship_candidates=1)
    )
    assert query._limit_clause.value == 1


def test_error_cycle_handling_is_rejected_by_sql_builder() -> None:
    with pytest.raises(ValueError, match="skip_seen"):
        build_bounded_relationship_traversal(
            _edge_scope(), (("chunk", "a"),), _profile(cycle_handling="error")
        )
