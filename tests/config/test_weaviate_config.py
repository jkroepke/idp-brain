from pathlib import Path

import pytest

from idp_brain.config.errors import ConfigValidationError
from idp_brain.config.weaviate import load_weaviate_config


def test_weaviate_config_derives_safe_versioned_collection_name() -> None:
    config = load_weaviate_config(Path("config/weaviate.yaml"))

    assert config.collection.name == "EvidenceChunk_Mvp1"
    assert config.collection.named_vectors == ("content",)
    assert config.endpoint.http_host == "127.0.0.1"
    assert config.backup.backend == "filesystem"
    assert config.collection.vector_index_type == "hnsw"
    assert config.collection.vector_distance == "cosine"
    assert config.collection.vector_quantizer == "none"


@pytest.mark.parametrize("generation", ["../../escape", "lowercase", "Bad_Name"])
def test_weaviate_config_rejects_unsafe_generation(
    generation: str, tmp_path: Path
) -> None:
    source = Path("config/weaviate.yaml").read_text(encoding="utf-8")
    path = tmp_path / "weaviate.yaml"
    path.write_text(source.replace("generation: Mvp1", f"generation: {generation}"))

    with pytest.raises(ConfigValidationError, match="generation"):
        load_weaviate_config(path)
