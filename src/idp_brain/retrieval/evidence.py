"""Strict sanitized evidence bundle contract and assembly boundary."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal, Protocol
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from idp_brain.ingestion.runs import sanitize_diagnostic_text
from idp_brain.models import Chunk, ClaimConflict, Source
from idp_brain.retrieval.corpus_filters import (
    TrustedCorpusScope,
    build_filtered_chunk_scope,
    build_filtered_citation_scope,
    build_filtered_claim_scope,
)
from idp_brain.retrieval.models import FusedCandidate, RetrievalFilters


class ContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class RelationshipPathItem(ContractModel):
    relationship_type: str
    direction: Literal["outbound", "inbound"]
    depth: int = Field(ge=1, le=3)
    source_id: str
    target_id: str
    citation_ids: tuple[str, ...] = Field(min_length=1)


class EvidenceItem(ContractModel):
    item_id: str
    item_kind: Literal["chunk", "memory"] = "chunk"
    sanitized_excerpt: str
    citation_ids: tuple[str, ...] = Field(min_length=1)
    sanitized_content_hash: str = Field(min_length=1)
    redaction_status: str
    authority_rank: int | None = None
    freshness: str | None = None
    relationship_path: tuple[RelationshipPathItem, ...] = ()


class CitationDTO(ContractModel):
    citation_id: str
    source_id: str
    source_version_id: str
    item_id: str
    source_url: str
    source_type: str
    commit_sha: str | None = None
    tag: str | None = None
    version: str | None = None
    checksum: str | None = None
    locator: str
    line_start: int | None = None
    line_end: int | None = None
    sanitized_content_hash: str = Field(min_length=1)
    redaction_status: str
    visibility_label: str
    corpus_eligibility_label: str

    @field_validator("source_url")
    @classmethod
    def source_url_must_not_expose_a_local_path(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("citation source_url requires an allowed remote scheme")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "citation source_url cannot contain credentials or query data"
            )
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

    @field_validator(
        "source_id",
        "source_version_id",
        "item_id",
        "source_type",
        "commit_sha",
        "tag",
        "version",
        "checksum",
        "locator",
        "redaction_status",
        "visibility_label",
        "corpus_eligibility_label",
    )
    @classmethod
    def provenance_strings_are_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(not char.isprintable() for char in value) or re.search(
            r"(?i)\b(token|secret|password|credential|api[_-]?key)\b", value
        ):
            raise ValueError("citation provenance contains unsafe text")
        if value.startswith(("/", "~", "\\")) or (
            len(value) > 2 and value[1:3] == ":\\"
        ):
            raise ValueError("citation provenance cannot contain a local path")
        return value


# Public contract name requested by the plan; kept separate from the ORM class.
Citation = CitationDTO


class CorpusEligibilityFilterResult(ContractModel):
    applied: bool = True
    policy_dimensions: tuple[str, ...]
    selected_eligible_count: int = Field(ge=0)


class ConflictMarker(ContractModel):
    conflict_id: str
    status: str
    competing_item_ids: tuple[str, ...] = Field(min_length=2)
    competing_citation_ids: tuple[str, ...] = Field(min_length=2)


class RetrievalDiagnostics(ContractModel):
    query_profile_id: str
    active_index_version_id: str | None
    retrieval_paths: tuple[str, ...]
    selected_candidate_count: int = Field(ge=0)
    dropped_missing_evidence_count: int = Field(ge=0)
    filters_applied: tuple[str, ...]
    candidates: tuple[CandidateDiagnostics, ...] = ()


class CandidateDiagnostics(ContractModel):
    item_id: str
    fused_rank: int | None
    reranked_rank: int | None
    fused_score: float
    rerank_score: float | None
    retrieval_paths: tuple[str, ...]


class TokenBudgetEstimate(ContractModel):
    budget_tokens: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    truncated_item_count: int = Field(ge=0)
    estimation_method: Literal["characters_div_4_ceiling"] = "characters_div_4_ceiling"


class EvidenceBundle(ContractModel):
    query: str
    normalized_query_intent: Mapping[str, tuple[str, ...] | str | bool]
    selected_chunk_ids: tuple[str, ...]
    selected_memory_item_ids: tuple[str, ...]
    evidence_items: tuple[EvidenceItem, ...]
    citations: tuple[CitationDTO, ...]
    conflict_markers: tuple[ConflictMarker, ...]
    corpus_eligibility: CorpusEligibilityFilterResult
    diagnostics: RetrievalDiagnostics
    token_budget: TokenBudgetEstimate


@dataclass(frozen=True)
class TrustedEvidenceRecord:
    """Fetcher output from already filtered canonical sanitized tables."""

    item_id: str
    sanitized_text: str
    sanitized_content_hash: str
    citation_ids: tuple[str, ...]
    redaction_status: str
    source_id: str
    source_version_id: str
    corpus_eligibility_label: str
    authority_rank: int | None = None
    freshness: str | None = None
    item_kind: Literal["chunk", "memory"] = "chunk"


class EvidenceFetcher(Protocol):
    def fetch(
        self,
        candidate_ids: Sequence[str],
        filters: RetrievalFilters,
        query_profile_id: str,
    ) -> tuple[
        Mapping[str, TrustedEvidenceRecord],
        Mapping[str, CitationDTO],
        Sequence[ConflictMarker],
    ]: ...


class EvidenceAssembler:
    def __init__(self, fetcher: EvidenceFetcher) -> None:
        self._fetcher = fetcher

    def assemble(
        self,
        *,
        query: str,
        normalized_query_intent: Mapping[str, tuple[str, ...] | str | bool],
        candidates: Sequence[FusedCandidate],
        query_profile_id: str,
        active_index_version_id: str | None,
        token_budget: int,
        filters_applied: Sequence[str],
        filters: RetrievalFilters,
    ) -> EvidenceBundle:
        ids = tuple(candidate.chunk_id for candidate in candidates)
        records, citations, conflicts = self._fetcher.fetch(
            ids, filters, query_profile_id
        )
        remaining_chars = token_budget * 4
        items: list[EvidenceItem] = []
        truncated = dropped = 0
        used_citations: set[str] = set()
        candidate_by_id = {item.chunk_id: item for item in candidates}
        for candidate_id in ids:
            record = records.get(candidate_id)
            if not _record_is_usable(record, citations):
                dropped += 1
                continue
            assert record is not None
            excerpt = record.sanitized_text[:remaining_chars]
            truncated += int(len(excerpt) < len(record.sanitized_text))
            remaining_chars = max(0, remaining_chars - len(excerpt))
            if not excerpt:
                dropped += 1
                continue
            relationship = _relationship_path(
                candidate_by_id[candidate_id], set(record.citation_ids)
            )
            if relationship is None:
                dropped += 1
                continue
            used_citations.update(record.citation_ids)
            items.append(
                EvidenceItem(
                    item_id=record.item_id,
                    item_kind=record.item_kind,
                    sanitized_excerpt=excerpt,
                    citation_ids=record.citation_ids,
                    sanitized_content_hash=record.sanitized_content_hash,
                    redaction_status=record.redaction_status,
                    authority_rank=record.authority_rank,
                    freshness=record.freshness,
                    relationship_path=relationship,
                )
            )
        citation_items = tuple(
            citations[citation_id] for citation_id in sorted(used_citations)
        )
        item_ids = {item.item_id for item in items}
        allowed_conflicts = tuple(
            marker
            for marker in sorted(conflicts, key=lambda value: value.conflict_id)
            if set(marker.competing_item_ids).issubset(item_ids)
            and set(marker.competing_citation_ids).issubset(used_citations)
        )
        text_chars = sum(len(item.sanitized_excerpt) for item in items)
        paths = tuple(
            sorted(
                {path for candidate in candidates for path in candidate.path_candidates}
            )
        )
        return EvidenceBundle(
            query=sanitize_diagnostic_text(query),
            normalized_query_intent=normalized_query_intent,
            selected_chunk_ids=tuple(
                item.item_id for item in items if item.item_kind == "chunk"
            ),
            selected_memory_item_ids=tuple(
                item.item_id for item in items if item.item_kind == "memory"
            ),
            evidence_items=tuple(items),
            citations=citation_items,
            conflict_markers=allowed_conflicts,
            corpus_eligibility=CorpusEligibilityFilterResult(
                policy_dimensions=tuple(filters_applied),
                selected_eligible_count=len(items),
            ),
            diagnostics=RetrievalDiagnostics(
                query_profile_id=query_profile_id,
                active_index_version_id=active_index_version_id,
                retrieval_paths=paths,
                selected_candidate_count=len(items),
                dropped_missing_evidence_count=dropped,
                filters_applied=tuple(filters_applied),
                candidates=tuple(
                    CandidateDiagnostics(
                        item_id=item.item_id,
                        fused_rank=candidate_by_id[item.item_id].fused_rank,
                        reranked_rank=candidate_by_id[item.item_id].reranked_rank,
                        fused_score=candidate_by_id[item.item_id].fused_score,
                        rerank_score=candidate_by_id[item.item_id].rerank_score,
                        retrieval_paths=tuple(
                            sorted(candidate_by_id[item.item_id].path_candidates)
                        ),
                    )
                    for item in items
                ),
            ),
            token_budget=TokenBudgetEstimate(
                budget_tokens=token_budget,
                estimated_tokens=(text_chars + 3) // 4,
                truncated_item_count=truncated,
            ),
        )


def _record_is_usable(
    record: TrustedEvidenceRecord | None, citations: Mapping[str, CitationDTO]
) -> bool:
    return bool(
        record
        and record.sanitized_text
        and record.sanitized_content_hash
        and record.citation_ids
        and all(
            citation_id in citations
            and citations[citation_id].item_id == record.item_id
            and citations[citation_id].source_id == record.source_id
            and citations[citation_id].source_version_id == record.source_version_id
            and citations[citation_id].corpus_eligibility_label
            == record.corpus_eligibility_label
            and citations[citation_id].sanitized_content_hash
            and citations[citation_id].sanitized_content_hash
            == record.sanitized_content_hash
            for citation_id in record.citation_ids
        )
    )


class SQLAlchemyEvidenceFetcher:
    """Canonical evidence fetcher whose candidate predicates follow policy scopes."""

    def __init__(self, session: Session, *, trusted_scope: TrustedCorpusScope) -> None:
        self._session = session
        self._trusted_scope = trusted_scope

    def fetch(
        self,
        candidate_ids: Sequence[str],
        filters: RetrievalFilters,
        query_profile_id: str,
    ) -> tuple[
        Mapping[str, TrustedEvidenceRecord],
        Mapping[str, CitationDTO],
        Sequence[ConflictMarker],
    ]:
        chunk_scope = build_filtered_chunk_scope(
            self._session,
            filters,
            trusted=self._trusted_scope,
            columns=_evidence_chunk_columns(),
        )
        citation_scope = build_filtered_citation_scope(
            chunk_scope, filters, self._trusted_scope
        )
        chunk_rows = self._session.execute(
            select(chunk_scope).where(chunk_scope.c.chunk_id.in_(tuple(candidate_ids)))
        ).mappings()
        records = {
            row["chunk_id"]: TrustedEvidenceRecord(
                item_id=row["chunk_id"],
                sanitized_text=row["sanitized_text"],
                sanitized_content_hash=row["sanitized_content_hash"],
                citation_ids=(),
                redaction_status=row["redaction_status"],
                source_id=row["source_id"],
                source_version_id=row["source_version_id"],
                corpus_eligibility_label=row["corpus_eligibility_label"],
                authority_rank=row["authority_rank"],
                freshness=row["freshness"].isoformat()
                if row["freshness"] is not None
                else None,
            )
            for row in chunk_rows
        }
        citation_rows = list(
            self._session.execute(
                select(citation_scope).where(
                    citation_scope.c.chunk_id.in_(tuple(candidate_ids))
                )
            ).mappings()
        )
        citation_map: dict[str, CitationDTO] = {}
        for row in citation_rows:
            try:
                citation = _citation_from_row(row)
            except ValidationError:
                continue
            citation_map[citation.citation_id] = citation
        citation_ids_by_chunk: dict[str, list[str]] = {}
        for citation in citation_map.values():
            citation_ids_by_chunk.setdefault(citation.item_id, []).append(
                citation.citation_id
            )
        records = {
            item_id: replace(
                record,
                citation_ids=tuple(sorted(citation_ids_by_chunk.get(item_id, ()))),
            )
            for item_id, record in records.items()
        }
        conflicts = self._conflicts(
            citation_scope, filters, citation_map, query_profile_id
        )
        return records, citation_map, conflicts

    def _conflicts(
        self,
        citation_scope: object,
        filters: RetrievalFilters,
        citations: Mapping[str, CitationDTO],
        query_profile_id: str,
    ) -> list[ConflictMarker]:
        if query_profile_id != "conflict_search":
            return []
        claims = build_filtered_claim_scope(
            citation_scope, filters, self._trusted_scope
        )
        left = claims.alias("eligible_left_claim")
        right = claims.alias("eligible_right_claim")
        rows = self._session.execute(
            select(
                ClaimConflict.id,
                ClaimConflict.status,
                left.c.primary_citation_id.label("left_citation_id"),
                right.c.primary_citation_id.label("right_citation_id"),
            )
            .join(left, left.c.id == ClaimConflict.left_claim_id)
            .join(right, right.c.id == ClaimConflict.right_claim_id)
            .where(
                or_(
                    left.c.primary_citation_id.in_(tuple(citations)),
                    right.c.primary_citation_id.in_(tuple(citations)),
                )
            )
        ).mappings()
        result = []
        for row in rows:
            citation_ids = (row["left_citation_id"], row["right_citation_id"])
            if not all(citation_id in citations for citation_id in citation_ids):
                raise ValueError("conflict evidence is incomplete after filtering")
            result.append(
                ConflictMarker(
                    conflict_id=row["id"],
                    status=row["status"],
                    competing_item_ids=tuple(
                        citations[citation_id].item_id for citation_id in citation_ids
                    ),
                    competing_citation_ids=citation_ids,
                )
            )
        return result


def _relationship_path(
    candidate: FusedCandidate, allowed_citations: set[str]
) -> tuple[RelationshipPathItem, ...] | None:
    relationship = candidate.path_candidates.get("relationship")
    if relationship is None:
        return ()
    raw_path = relationship.diagnostics.get("relationship_path", ())
    if not isinstance(raw_path, (tuple, list)) or not raw_path:
        return None
    result: list[RelationshipPathItem] = []
    previous: str | None = None
    visited: set[str] = set()
    for expected_depth, edge in enumerate(raw_path, 1):
        if not isinstance(edge, dict):
            return None
        try:
            item = RelationshipPathItem(
                relationship_type=edge["relationship_type"],
                direction=edge["direction"],
                depth=edge["depth"],
                source_id=edge["from_id"],
                target_id=edge["to_id"],
                citation_ids=tuple(edge["citation_ids"]),
            )
        except KeyError, TypeError, ValidationError:
            return None
        if (
            item.depth != expected_depth
            or (previous is not None and item.source_id != previous)
            or not set(item.citation_ids).issubset(allowed_citations)
        ):
            return None
        if not visited:
            visited.add(item.source_id)
        if item.target_id in visited:
            return None
        visited.add(item.target_id)
        previous = item.target_id
        result.append(item)
    if previous != candidate.chunk_id:
        return None
    return tuple(result)


def _evidence_chunk_columns() -> tuple[object, ...]:
    return (
        Chunk.id.label("chunk_id"),
        Chunk.sanitized_text,
        Chunk.sanitized_content_hash,
        Chunk.source_id,
        Chunk.source_version_id,
        Chunk.source_type,
        Chunk.redaction_status,
        Chunk.corpus_eligibility_label,
        Chunk.first_seen_at.label("freshness"),
        select(Source.authority_rank)
        .where(Source.id == Chunk.source_id)
        .scalar_subquery()
        .label("authority_rank"),
    )


def _citation_from_row(row: RowMapping) -> CitationDTO:
    source_url = row.get("artifact_url") or row.get("repository_url")
    locator = row.get("logical_locator") or row.get("path")
    return CitationDTO(
        citation_id=str(row["id"]),
        source_id=str(row["source_id"]),
        source_version_id=str(row["source_version_id"]),
        item_id=str(row["chunk_id"]),
        source_url=str(source_url),
        source_type=str(row["source_type"]),
        commit_sha=_optional_str(row.get("commit_sha")),
        tag=_optional_str(row.get("tag")),
        version=_optional_str(row.get("version")),
        checksum=_optional_str(row.get("checksum")),
        locator=str(locator),
        line_start=_optional_int(row.get("line_start")),
        line_end=_optional_int(row.get("line_end")),
        sanitized_content_hash=str(row["sanitized_content_hash"]),
        redaction_status=str(row["redaction_status"]),
        visibility_label=str(row["visibility_label"]),
        corpus_eligibility_label=str(row["corpus_eligibility_label"]),
    )


def _optional_str(value: object) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise ValueError("expected optional string provenance")


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ValueError("expected optional integer provenance")
