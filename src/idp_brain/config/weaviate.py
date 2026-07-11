"""Strict local Weaviate runtime configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from idp_brain.config.base import ConfigModel
from idp_brain.config.loader import load_typed_config

_GENERATION = re.compile(r"^[A-Z][A-Za-z0-9]{0,31}$")


class WeaviateEndpointConfig(ConfigModel):
    http_host: Literal["127.0.0.1", "localhost"]
    http_port: int = Field(ge=1, le=65535)
    grpc_host: Literal["127.0.0.1", "localhost"]
    grpc_port: int = Field(ge=1, le=65535)
    mcp_path: Literal["/v1/mcp"]


class WeaviateAuthConfig(ConfigModel):
    writer_user: str = Field(min_length=1)
    writer_api_key_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    reader_user: str = Field(min_length=1)
    reader_api_key_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")


class WeaviateCollectionConfig(ConfigModel):
    generation: str
    vectorizer: Literal["text2vec-transformers"]
    named_vectors: tuple[Literal["content"], ...]
    tokenization: Literal["word"]
    vector_index_type: Literal["hnsw"]
    vector_distance: Literal["cosine"]
    vector_quantizer: Literal["none"]

    @model_validator(mode="after")
    def validate_generation_and_vectors(self) -> WeaviateCollectionConfig:
        if not _GENERATION.fullmatch(self.generation):
            raise ValueError(
                "generation must start uppercase and contain only letters or digits"
            )
        if self.named_vectors != ("content",):
            raise ValueError("the MVP collection requires exactly the content vector")
        return self

    @property
    def name(self) -> str:
        return f"EvidenceChunk_{self.generation}"


class WeaviateBackupConfig(ConfigModel):
    backend: Literal["filesystem"]
    path: str = Field(pattern=r"^/var/lib/weaviate/backups(?:/.*)?$")


class WeaviateConfig(ConfigModel):
    config_version: Literal[1]
    kind: Literal["weaviate"]
    endpoint: WeaviateEndpointConfig
    authentication: WeaviateAuthConfig
    collection: WeaviateCollectionConfig
    backup: WeaviateBackupConfig


def load_weaviate_config(path: Path) -> WeaviateConfig:
    return load_typed_config(path, WeaviateConfig)
