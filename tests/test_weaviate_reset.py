import pytest

from idp_brain.weaviate_reset import resolved_weaviate_volume


def test_resolves_compose_project_specific_labeled_volume() -> None:
    metadata = {
        "services": {
            "weaviate": {
                "volumes": [
                    {
                        "source": "idp_brain_weaviate",
                        "target": "/var/lib/weaviate",
                    }
                ]
            }
        },
        "volumes": {
            "idp_brain_weaviate": {
                "name": "custom-project_idp_brain_weaviate",
                "labels": {
                    "idp-brain.scope": "local-development",
                    "idp-brain.disposable": "true",
                },
            }
        },
    }

    assert resolved_weaviate_volume(metadata) == "custom-project_idp_brain_weaviate"


@pytest.mark.parametrize("volume_definitions", [{}, {"data": {"name": "unsafe"}}])
def test_volume_resolution_fails_closed(volume_definitions: dict[str, object]) -> None:
    with pytest.raises(RuntimeError, match="exactly one"):
        resolved_weaviate_volume(
            {
                "services": {
                    "weaviate": {
                        "volumes": [{"source": "data", "target": "/var/lib/weaviate"}]
                    }
                },
                "volumes": volume_definitions,
            }
        )


def test_volume_resolution_rejects_multiple_candidates() -> None:
    labels = {
        "idp-brain.scope": "local-development",
        "idp-brain.disposable": "true",
    }
    with pytest.raises(RuntimeError, match="found 2"):
        resolved_weaviate_volume(
            {
                "services": {
                    "weaviate": {
                        "volumes": [
                            {"source": "one", "target": "/var/lib/weaviate"},
                            {"source": "two", "target": "/var/lib/weaviate"},
                        ]
                    }
                },
                "volumes": {
                    "one": {"name": "project_one", "labels": labels},
                    "two": {"name": "project_two", "labels": labels},
                },
            }
        )
