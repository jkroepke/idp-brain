from __future__ import annotations

from pathlib import Path

from idp_brain.config import load_config_dir


def test_embedding_profiles_use_explicit_4_1_contract() -> None:
    bundle = load_config_dir(Path("config"))
    profiles = {
        profile.profile_id: profile for profile in bundle.models.embedding_profiles
    }

    for profile_id in [
        "docs_default",
        "docs_quality",
        "code_default",
        "memory_default",
    ]:
        profile = profiles[profile_id]
        assert profile.provider_id == "mock"
        assert profile.model_name
        assert profile.dimensions > 0
        assert profile.batch_size > 0
        assert profile.timeout_seconds > 0
        assert profile.external is False
        assert profile.required_env_vars == []
