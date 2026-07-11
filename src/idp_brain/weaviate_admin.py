"""Bootstrap the concrete local Weaviate collection."""

from __future__ import annotations

import os
from pathlib import Path

import weaviate
from weaviate.auth import Auth

from idp_brain.config.weaviate import load_weaviate_config
from idp_brain.weaviate_slice import bootstrap_collection, configure_reader_role


def main() -> None:
    config = load_weaviate_config(Path("config/weaviate.yaml"))
    key = os.environ.get(config.authentication.writer_api_key_env)
    if key is None:
        key = "local-mvp52-writer-key"
    with weaviate.connect_to_custom(
        http_host=config.endpoint.http_host,
        http_port=config.endpoint.http_port,
        http_secure=False,
        grpc_host=config.endpoint.grpc_host,
        grpc_port=config.endpoint.grpc_port,
        grpc_secure=False,
        auth_credentials=Auth.api_key(key),
    ) as client:
        if not client.is_ready():
            raise RuntimeError("local Weaviate is not ready")
        bootstrap_collection(client, config.collection)
        configure_reader_role(
            client,
            reader_user=config.authentication.reader_user,
            collection_name=config.collection.name,
        )
    print(f"Bootstrapped {config.collection.name}")


if __name__ == "__main__":
    main()
