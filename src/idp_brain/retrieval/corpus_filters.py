"""Fail-closed SQL scopes shared by every retrieval path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    String,
    and_,
    cast,
    column,
    exists,
    func,
    literal,
    select,
    union_all,
    values,
)
from sqlalchemy.orm import Session

from idp_brain.models import (
    Chunk,
    ChunkVersion,
    Citation,
    Claim,
    ClaimVersion,
    Fact,
    FactVersion,
    IndexVersion,
    Relationship,
    RelationshipVersion,
)
from idp_brain.retrieval.models import RetrievalFilterSet


@dataclass(frozen=True)
class TrustedCorpusScope:
    """Server-derived corpus authority; request data may only narrow it."""

    source_ids: tuple[str, ...] = ()
    source_types: tuple[str, ...] = ()
    visibility_labels: tuple[str, ...] = ("invited_users",)
    sensitivity_classes: tuple[str, ...] = ("public",)
    license_policy_statuses: tuple[str, ...] = ("allowed",)
    license_ids: tuple[str, ...] = ("MIT", "Apache-2.0")
    redaction_statuses: tuple[str, ...] = ("redacted", "not_required")
    corpus_eligibility_labels: tuple[str, ...] = (
        "allowed",
        "default_retrievable",
        "eligible",
    )


def _intersection(
    requested: tuple[str, ...], trusted: tuple[str, ...]
) -> tuple[str, ...]:
    if not requested:
        return trusted
    if not trusted:
        return requested
    return tuple(value for value in requested if value in trusted)


def narrow_filters(
    trusted: TrustedCorpusScope, filters: RetrievalFilterSet
) -> RetrievalFilterSet:
    """Intersect request filters with trusted policy without allowing expansion."""

    updates = {
        name: _intersection(getattr(filters, name), getattr(trusted, name))
        for name in (
            "source_ids",
            "source_types",
            "visibility_labels",
            "sensitivity_classes",
            "license_policy_statuses",
            "license_ids",
            "redaction_statuses",
            "corpus_eligibility_labels",
        )
    }
    # An explicitly requested but disallowed value must produce an empty scope.
    for name, value in updates.items():
        if getattr(filters, name) and not value:
            updates[name] = ("__no_trusted_match__",)
    return filters.model_copy(update=updates)


def resolve_active_index_filters(
    session: Session,
    filters: RetrievalFilterSet,
    *,
    required: bool = False,
    expected_kind: str | None = None,
    expected_profile: str | None = None,
) -> RetrievalFilterSet:
    if filters.active_index_version_id is None:
        if required:
            return filters.model_copy(update={"source_ids": ("__no_active_index__",)})
        return filters
    index = session.get(IndexVersion, filters.active_index_version_id)
    configured_profile = None
    if expected_kind == "vector":
        configured_profile = index.vector_profile if index is not None else None
    elif expected_kind == "bm25":
        configured_profile = index.bm25_profile if index is not None else None
    elif expected_kind == "exact":
        configured_profile = index.exact_index_profile if index is not None else None
    if (
        index is None
        or index.status != "active"
        or (
            expected_kind is not None
            and index.index_kind not in {expected_kind, "hybrid"}
        )
        or (expected_profile is not None and configured_profile != expected_profile)
    ):
        return filters.model_copy(update={"source_ids": ("__no_active_index__",)})
    indexed = tuple(index.source_scope.get("source_ids") or ())
    if not indexed:
        return filters
    requested = filters.source_ids or indexed
    narrowed = tuple(value for value in requested if value in indexed)
    return filters.model_copy(
        update={"source_ids": narrowed or ("__no_active_index__",)}
    )


def chunk_filter_clauses(
    session: Session,
    filters: RetrievalFilterSet,
    trusted: TrustedCorpusScope,
) -> list[Any]:
    narrowed = narrow_filters(trusted, filters)
    narrowed = resolve_active_index_filters(session, narrowed)
    current = exists(
        select(literal(1)).where(
            ChunkVersion.chunk_id == Chunk.id,
            ChunkVersion.is_current.is_(True),
            ChunkVersion.tombstoned_at.is_(None),
        )
    )
    citation = exists(
        select(literal(1)).where(
            Citation.chunk_id == Chunk.id,
            Citation.source_version_id == Chunk.source_version_id,
            Citation.source_id == Chunk.source_id,
            Citation.source_type == Chunk.source_type,
            Citation.source_allowlisted.is_(True),
            Citation.visibility_label.in_(narrowed.visibility_labels),
            Citation.sensitivity_class.in_(narrowed.sensitivity_classes),
            Citation.license_policy_status.in_(narrowed.license_policy_statuses),
            Citation.license_id.in_(narrowed.license_ids),
            Citation.redaction_status.in_(narrowed.redaction_statuses),
            Citation.corpus_eligibility_label.in_(narrowed.corpus_eligibility_labels),
        )
    )
    clauses = [
        Chunk.source_allowlisted.is_(True),
        Chunk.source_version_id.is_not(None),
        Chunk.sanitized_text.is_not(None),
        Chunk.sanitized_text != "",
        current,
        citation,
        Chunk.visibility_label.in_(narrowed.visibility_labels),
        Chunk.sensitivity_class.in_(narrowed.sensitivity_classes),
        Chunk.license_policy_status.in_(narrowed.license_policy_statuses),
        Chunk.license_id.in_(narrowed.license_ids),
        Chunk.redaction_status.in_(narrowed.redaction_statuses),
        Chunk.corpus_eligibility_label.in_(narrowed.corpus_eligibility_labels),
    ]
    for value, filter_column in (
        (narrowed.source_ids, Chunk.source_id),
        (narrowed.source_types, Chunk.source_type),
        (narrowed.version_labels, Chunk.version_label),
    ):
        if value:
            clauses.append(filter_column.in_(value))
    if narrowed.version_from is not None:
        clauses.append(Chunk.version_label >= narrowed.version_from)
    if narrowed.version_to is not None:
        clauses.append(Chunk.version_label <= narrowed.version_to)
    if narrowed.release_from is not None:
        clauses.append(Chunk.version_label >= narrowed.release_from)
    if narrowed.release_to is not None:
        clauses.append(Chunk.version_label <= narrowed.release_to)
    if narrowed.time_from is not None:
        clauses.append(Chunk.first_seen_at >= narrowed.time_from)
    if narrowed.time_to is not None:
        clauses.append(Chunk.first_seen_at <= narrowed.time_to)
    if not narrowed.source_allowlisted:
        clauses.append(literal(False))
    return clauses


def build_filtered_chunk_scope(
    session: Session,
    filters: RetrievalFilterSet,
    profile: Any | None = None,
    *,
    trusted: TrustedCorpusScope,
    columns: tuple[Any, ...] = (),
) -> Any:
    """Materialized CTE evaluated before candidate-specific predicates."""

    del profile
    selected = columns or (
        Chunk.id.label("chunk_id"),
        Chunk.source_id,
        Chunk.source_version_id,
        Chunk.source_type,
    )
    return (
        select(*selected)
        .where(and_(*chunk_filter_clauses(session, filters, trusted)))
        .cte("filtered_chunks")
        .prefix_with("MATERIALIZED", dialect="postgresql")
    )


def build_filtered_citation_scope(
    filtered_chunk_scope: Any,
    filters: RetrievalFilterSet,
    trusted: TrustedCorpusScope,
) -> Any:
    narrowed = narrow_filters(trusted, filters)
    return (
        select(Citation)
        .join(
            filtered_chunk_scope, filtered_chunk_scope.c.chunk_id == Citation.chunk_id
        )
        .where(
            Citation.source_allowlisted.is_(True),
            Citation.visibility_label.in_(narrowed.visibility_labels),
            Citation.sensitivity_class.in_(narrowed.sensitivity_classes),
            Citation.license_policy_status.in_(narrowed.license_policy_statuses),
            Citation.license_id.in_(narrowed.license_ids),
            Citation.redaction_status.in_(narrowed.redaction_statuses),
            Citation.corpus_eligibility_label.in_(narrowed.corpus_eligibility_labels),
            Citation.source_id == filtered_chunk_scope.c.source_id,
            Citation.source_version_id == filtered_chunk_scope.c.source_version_id,
        )
        .cte("filtered_citations")
    )


def _record_policy_clauses(record: Any, narrowed: RetrievalFilterSet) -> list[Any]:
    clauses = [
        record.source_allowlisted.is_(True),
        record.source_version_id.is_not(None),
        record.visibility_label.in_(narrowed.visibility_labels),
        record.sensitivity_class.in_(narrowed.sensitivity_classes),
        record.license_policy_status.in_(narrowed.license_policy_statuses),
        record.license_id.in_(narrowed.license_ids),
        record.redaction_status.in_(narrowed.redaction_statuses),
    ]
    if hasattr(record, "corpus_eligibility_label"):
        clauses.append(
            record.corpus_eligibility_label.in_(narrowed.corpus_eligibility_labels)
        )
    for values_, field in (
        (narrowed.source_ids, record.source_id),
        (narrowed.source_types, record.source_type),
        (narrowed.version_labels, record.version_label),
    ):
        if values_:
            clauses.append(field.in_(values_))
    if narrowed.version_from is not None:
        clauses.append(record.version_label >= narrowed.version_from)
    if narrowed.version_to is not None:
        clauses.append(record.version_label <= narrowed.version_to)
    if narrowed.release_from is not None:
        clauses.append(record.version_label >= narrowed.release_from)
    if narrowed.release_to is not None:
        clauses.append(record.version_label <= narrowed.release_to)
    if narrowed.time_from is not None:
        clauses.append(record.first_seen_at >= narrowed.time_from)
    if narrowed.time_to is not None:
        clauses.append(record.first_seen_at <= narrowed.time_to)
    return clauses


def build_filtered_claim_scope(
    filtered_citation_scope: Any,
    filters: RetrievalFilterSet,
    trusted: TrustedCorpusScope,
) -> Any:
    narrowed = narrow_filters(trusted, filters)
    current = exists(
        select(literal(1)).where(
            ClaimVersion.claim_id == Claim.id,
            ClaimVersion.is_current.is_(True),
            ClaimVersion.tombstoned_at.is_(None),
        )
    )
    return (
        select(Claim)
        .join(
            filtered_citation_scope,
            filtered_citation_scope.c.id == Claim.primary_citation_id,
        )
        .where(
            current,
            Claim.source_id == filtered_citation_scope.c.source_id,
            Claim.source_version_id == filtered_citation_scope.c.source_version_id,
            *_record_policy_clauses(Claim, narrowed),
        )
        .cte("filtered_claims")
    )


def build_filtered_fact_scope(
    filtered_citation_scope: Any,
    filters: RetrievalFilterSet,
    trusted: TrustedCorpusScope,
) -> Any:
    """Restrict facts to current versions backed by an eligible citation."""
    current = exists(
        select(literal(1)).where(
            FactVersion.fact_id == Fact.id,
            FactVersion.is_current.is_(True),
            FactVersion.tombstoned_at.is_(None),
        )
    )
    narrowed = narrow_filters(trusted, filters)
    return (
        select(Fact)
        .join(
            filtered_citation_scope,
            filtered_citation_scope.c.id == Fact.primary_citation_id,
        )
        .where(
            current,
            Fact.source_id == filtered_citation_scope.c.source_id,
            Fact.source_version_id == filtered_citation_scope.c.source_version_id,
            *_record_policy_clauses(Fact, narrowed),
        )
        .cte("filtered_facts")
    )


def build_filtered_entity_scope(
    filtered_chunk_scope: Any,
    filtered_claim_scope: Any | None = None,
    filtered_fact_scope: Any | None = None,
) -> Any:
    """Return typed eligible normalized endpoints; unknown types fail closed."""
    endpoints = [
        select(
            literal("chunk").label("entity_type"),
            filtered_chunk_scope.c.chunk_id.label("entity_id"),
        )
    ]
    if filtered_claim_scope is not None:
        endpoints.append(select(literal("claim"), filtered_claim_scope.c.id))
    if filtered_fact_scope is not None:
        endpoints.append(select(literal("fact"), filtered_fact_scope.c.id))
    return union_all(*endpoints).cte("filtered_entities")


def build_filtered_relationship_scope(
    filtered_citation_scope: Any,
    filtered_entity_scope: Any,
    *,
    filters: RetrievalFilterSet,
    trusted: TrustedCorpusScope,
    relationship_types: tuple[str, ...] = (),
) -> Any:
    from_ep = filtered_entity_scope.alias("eligible_from")
    to_ep = filtered_entity_scope.alias("eligible_to")
    current = exists(
        select(literal(1)).where(
            RelationshipVersion.relationship_id == Relationship.id,
            RelationshipVersion.is_current.is_(True),
            RelationshipVersion.tombstoned_at.is_(None),
        )
    )
    narrowed = narrow_filters(trusted, filters)
    clauses = [
        current,
        Relationship.source_id == filtered_citation_scope.c.source_id,
        Relationship.source_version_id == filtered_citation_scope.c.source_version_id,
        *_record_policy_clauses(Relationship, narrowed),
    ]
    if relationship_types:
        clauses.append(Relationship.relationship_type.in_(relationship_types))
    return (
        select(Relationship)
        .join(
            filtered_citation_scope,
            filtered_citation_scope.c.id == Relationship.primary_citation_id,
        )
        .join(
            from_ep,
            and_(
                from_ep.c.entity_type == Relationship.from_entity_type,
                from_ep.c.entity_id == Relationship.from_entity_id,
            ),
        )
        .join(
            to_ep,
            and_(
                to_ep.c.entity_type == Relationship.to_entity_type,
                to_ep.c.entity_id == Relationship.to_entity_id,
            ),
        )
        .where(and_(*clauses))
        .cte("filtered_relationships")
    )


def build_bounded_relationship_traversal(
    filtered_relationship_scope: Any,
    seed_entities: tuple[tuple[str, str], ...],
    profile: Any,
) -> Any:
    """Build a cycle-safe recursive traversal over an eligible edge scope.

    The supplied profile is the existing ``RelationshipTraversalConfig`` contract.
    Disabled or seedless traversals return an empty selectable.
    """

    if not profile.enabled or not seed_entities:
        return select(
            literal(None).label("relationship_id"),
            literal(None).label("entity_type"),
            literal(None).label("entity_id"),
            literal(0).label("depth"),
        ).where(literal(False))
    if profile.cycle_handling != "skip_seen":
        raise ValueError(
            "SQL relationship traversal requires cycle_handling='skip_seen'"
        )

    edges = (
        select(filtered_relationship_scope)
        .where(
            filtered_relationship_scope.c.relationship_type.in_(
                tuple(profile.relationship_types)
            )
        )
        .cte("typed_relationship_edges")
    )
    orientations: list[Any] = []
    if profile.direction in {"outbound", "both"}:
        orientations.append(
            select(
                edges.c.id.label("relationship_id"),
                edges.c.from_entity_type.label("from_type"),
                edges.c.from_entity_id.label("from_id"),
                edges.c.to_entity_type.label("to_type"),
                edges.c.to_entity_id.label("to_id"),
            )
        )
    if profile.direction in {"inbound", "both"}:
        orientations.append(
            select(
                edges.c.id.label("relationship_id"),
                edges.c.to_entity_type.label("from_type"),
                edges.c.to_entity_id.label("from_id"),
                edges.c.from_entity_type.label("to_type"),
                edges.c.from_entity_id.label("to_id"),
            )
        )
    oriented = union_all(*orientations)
    oriented_edges = oriented.cte("oriented_relationship_edges")
    ranked_edges = select(
        oriented_edges,
        func.row_number()
        .over(
            partition_by=(oriented_edges.c.from_type, oriented_edges.c.from_id),
            order_by=(oriented_edges.c.relationship_id, oriented_edges.c.to_id),
        )
        .label("fanout_rank"),
    ).cte("ranked_relationship_edges")
    bounded_edges = (
        select(ranked_edges)
        .where(ranked_edges.c.fanout_rank <= profile.max_fanout_per_seed)
        .cte("bounded_relationship_edges")
    )

    seed_values = values(
        column("entity_type", String),
        column("entity_id", String),
        column("visited_ids", String),
        column("candidate_ordinal"),
        name="seeds",
    ).data(
        [
            (entity_type, entity_id, f"|{entity_type}:{entity_id}|", index)
            for index, (entity_type, entity_id) in enumerate(seed_entities)
        ]
    )
    seed_query = select(
        literal(None).label("relationship_id"),
        seed_values.c.entity_type,
        seed_values.c.entity_id,
        literal(0).label("depth"),
        seed_values.c.visited_ids,
        seed_values.c.candidate_ordinal,
    )
    traversal = seed_query.cte("relationship_traversal", recursive=True)
    next_visited = (
        traversal.c.visited_ids
        + cast(bounded_edges.c.to_type, String)
        + literal(":")
        + cast(bounded_edges.c.to_id, String)
        + literal("|")
    )
    recursive = (
        select(
            bounded_edges.c.relationship_id,
            bounded_edges.c.to_type.label("entity_type"),
            bounded_edges.c.to_id.label("entity_id"),
            (traversal.c.depth + 1).label("depth"),
            next_visited.label("visited_ids"),
            (
                len(seed_entities)
                + traversal.c.candidate_ordinal * profile.max_fanout_per_seed
                + bounded_edges.c.fanout_rank
            ).label("candidate_ordinal"),
        )
        .join(
            bounded_edges,
            and_(
                bounded_edges.c.from_type == traversal.c.entity_type,
                bounded_edges.c.from_id == traversal.c.entity_id,
            ),
        )
        .where(
            traversal.c.depth < profile.max_depth,
            ~traversal.c.visited_ids.contains(
                literal("|")
                + cast(bounded_edges.c.to_type, String)
                + literal(":")
                + cast(bounded_edges.c.to_id, String)
                + literal("|")
            ),
            (
                len(seed_entities)
                + traversal.c.candidate_ordinal * profile.max_fanout_per_seed
                + bounded_edges.c.fanout_rank
            )
            <= profile.max_relationship_candidates,
        )
    )
    traversal = traversal.union_all(recursive)
    return (
        select(
            traversal.c.relationship_id,
            traversal.c.entity_type,
            traversal.c.entity_id,
            traversal.c.depth,
        )
        .where(traversal.c.relationship_id.is_not(None))
        .order_by(
            traversal.c.depth,
            traversal.c.relationship_id,
            traversal.c.entity_id,
        )
        .limit(profile.max_relationship_candidates)
    )


def post_filter_chunk_count(filtered_chunk_scope: Any) -> Any:
    """Count only records visible in the already-filtered corpus scope."""

    return select(func.count()).select_from(filtered_chunk_scope)
