"""Small, concrete Weaviate boundary for the MVP vertical slice."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from weaviate.classes.config import (
    Configure,
    DataType,
    Property,
    Tokenization,
    VectorDistances,
)
from weaviate.classes.query import MetadataQuery
from weaviate.classes.rbac import Permissions

from idp_brain.config.weaviate import WeaviateCollectionConfig
from idp_brain.ingestion.chunking import SanitizedChunk, SanitizedCitation
from idp_brain.ingestion.redaction_stage import SAFE_REDACTION_STATUSES

if TYPE_CHECKING:
    from weaviate.client import WeaviateClient

COLLECTION_NAME = "EvidenceChunk_Mvp1"
VECTOR_NAME = "content"
READER_ROLE = "evidence-mvp52-reader"
_UUID_NAMESPACE = uuid.UUID("92c967cf-cf26-5f36-b110-7aac6bbf6045")
_TEXT_PROPERTY_NAMES = (
    "chunkId",
    "content",
    "contentKind",
    "title",
    "headingPath",
    "sourceId",
    "sourceType",
    "sourceUrl",
    "sourceVersion",
    "artifactPath",
    "logicalLocator",
    "symbolPath",
    "signature",
    "language",
    "extractorVersion",
    "chunkingProfile",
    "contentHash",
    "redactionStatus",
    "citationId",
)


class IncompatibleCollectionError(RuntimeError):
    """Raised when an existing generation does not match its declared schema."""


@dataclass(frozen=True)
class EvidenceMatch:
    uuid: uuid.UUID
    properties: dict[str, object]
    score: float | None


def evidence_uuid(chunk_key: str) -> uuid.UUID:
    """Return the stable Weaviate identity for a stable chunk identity."""

    return uuid.uuid5(_UUID_NAMESPACE, chunk_key)


def bootstrap_collection(
    client: WeaviateClient,
    collection: WeaviateCollectionConfig,
) -> None:
    """Create or validate one immutable versioned evidence collection."""

    if client.collections.exists(collection.name):
        _validate_collection(client, collection)
        return
    client.collections.create(
        name=collection.name,
        properties=_schema_properties(collection),
        vector_config=Configure.Vectors.text2vec_transformers(
            name=VECTOR_NAME,
            source_properties=["content", "title", "headingPath"],
            vectorize_collection_name=False,
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances(collection.vector_distance),
                quantizer=Configure.VectorIndex.Quantizer.none(),
            ),
        ),
    )


def _schema_properties(
    collection: WeaviateCollectionConfig,
) -> list[Property]:
    tokenization = Tokenization(collection.tokenization)
    return [
        *(
            Property(name=name, data_type=DataType.TEXT, tokenization=tokenization)
            for name in _TEXT_PROPERTY_NAMES
        ),
        Property(name="lineStart", data_type=DataType.INT),
        Property(name="lineEnd", data_type=DataType.INT),
    ]


def _validate_collection(
    client: WeaviateClient, collection: WeaviateCollectionConfig
) -> None:
    actual = client.collections.use(collection.name).config.get()
    expected = {
        name: ("text", collection.tokenization) for name in _TEXT_PROPERTY_NAMES
    } | {"lineStart": ("int", None), "lineEnd": ("int", None)}
    observed = {
        prop.name: (
            prop.data_type.value,
            prop.tokenization.value if prop.tokenization else None,
        )
        for prop in actual.properties
    }
    vectors = set(actual.vector_config or {})
    vector = (actual.vector_config or {}).get(VECTOR_NAME)
    vectorizer_matches = (
        vector is not None
        and vector.vectorizer.vectorizer == collection.vectorizer
        and vector.vectorizer.source_properties == ["content", "title", "headingPath"]
    )
    index = vector.vector_index_config if vector is not None else None
    index_matches = (
        index is not None
        and index.__class__.__name__ == "_VectorIndexConfigHNSW"
        and index.distance_metric.value == collection.vector_distance
        and getattr(index, "quantizer", object()) is None
    )
    if (
        observed != expected
        or vectors != set(collection.named_vectors)
        or not vectorizer_matches
        or not index_matches
    ):
        raise IncompatibleCollectionError(
            f"{collection.name} is incompatible; choose a new collection generation"
        )


def configure_reader_role(
    client: WeaviateClient,
    *,
    reader_user: str,
    collection_name: str = COLLECTION_NAME,
) -> None:
    """Grant one local identity only the permissions needed for read-only MCP."""

    if client.roles.exists(READER_ROLE):
        client.roles.delete(READER_ROLE)
    client.roles.create(
        role_name=READER_ROLE,
        permissions=[
            Permissions.collections(collection=collection_name, read_config=True),
            Permissions.data(collection=collection_name, read=True),
            Permissions.mcp(read=True),
        ],
    )
    client.users.db.assign_roles(user_id=reader_user, role_names=READER_ROLE)


def upsert_evidence_chunk(
    client: WeaviateClient,
    chunk: SanitizedChunk,
    citation: SanitizedCitation,
    *,
    extractor_version: str,
    collection_name: str = COLLECTION_NAME,
) -> uuid.UUID:
    """Write one already-sanitized, self-contained evidence object."""

    if chunk.redaction_status not in SAFE_REDACTION_STATUSES:
        raise ValueError("only redacted chunks may cross the Weaviate boundary")
    object_uuid = evidence_uuid(chunk.chunk_key)
    data = client.collections.use(collection_name).data
    properties = _properties(chunk, citation, extractor_version)
    if data.exists(object_uuid):
        data.replace(uuid=object_uuid, properties=properties)
    else:
        data.insert(uuid=object_uuid, properties=properties)
    return object_uuid


def hybrid_search(
    client: WeaviateClient,
    query: str,
    *,
    limit: int = 5,
    collection_name: str = COLLECTION_NAME,
) -> tuple[EvidenceMatch, ...]:
    """Run the single direct hybrid query used by CLI and evaluation."""

    response = client.collections.use(collection_name).query.hybrid(
        query=query,
        limit=limit,
        target_vector=VECTOR_NAME,
        return_metadata=MetadataQuery(score=True),
    )
    return tuple(
        EvidenceMatch(
            uuid=item.uuid,
            properties=dict(item.properties),
            score=item.metadata.score,
        )
        for item in response.objects
    )


def _properties(
    chunk: SanitizedChunk,
    citation: SanitizedCitation,
    extractor_version: str,
) -> dict[str, str | int]:
    line_range = chunk.line_range
    title = chunk.heading_path or chunk.artifact_path
    return {
        "chunkId": chunk.chunk_key,
        "content": chunk.sanitized_text,
        "contentKind": chunk.chunk_kind,
        "title": title,
        "headingPath": chunk.heading_path or "",
        "sourceId": chunk.source_id,
        "sourceType": chunk.source_type,
        "sourceUrl": citation.source_url,
        "sourceVersion": chunk.source_version_id or "",
        "artifactPath": chunk.artifact_path,
        "logicalLocator": chunk.logical_locator,
        "symbolPath": chunk.symbol_path or "",
        "signature": chunk.signature_text or "",
        "language": chunk.language or "",
        "lineStart": line_range.start if line_range else 0,
        "lineEnd": line_range.end if line_range else 0,
        "extractorVersion": extractor_version,
        "chunkingProfile": chunk.chunker_profile,
        "contentHash": chunk.sanitized_content_hash,
        "redactionStatus": chunk.redaction_status,
        "citationId": citation.citation_key,
    }
