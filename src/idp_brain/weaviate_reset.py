"""Reset only the Compose-resolved disposable Weaviate volume."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping


def resolved_weaviate_volume(config: Mapping[str, object]) -> str:
    services = config.get("services")
    volumes = config.get("volumes")
    if not isinstance(services, dict) or not isinstance(volumes, dict):
        raise RuntimeError("Compose metadata is missing services or volumes")
    service = services.get("weaviate")
    if not isinstance(service, dict):
        raise RuntimeError("Compose metadata has no weaviate service")
    mounts = service.get("volumes")
    if not isinstance(mounts, list):
        raise RuntimeError("Weaviate has no resolved volume mounts")
    candidates: list[str] = []
    for mount in mounts:
        if not isinstance(mount, dict) or mount.get("target") != "/var/lib/weaviate":
            continue
        source = mount.get("source")
        definition = volumes.get(source) if isinstance(source, str) else None
        if not isinstance(definition, dict):
            continue
        labels = definition.get("labels")
        if not isinstance(labels, dict):
            continue
        if (
            labels.get("idp-brain.scope") != "local-development"
            or labels.get("idp-brain.disposable") != "true"
        ):
            continue
        name = definition.get("name")
        if isinstance(name, str):
            candidates.append(name)
    if len(candidates) != 1:
        raise RuntimeError(
            "expected exactly one labeled Weaviate data volume, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def main() -> None:
    metadata = json.loads(
        subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    volume = resolved_weaviate_volume(metadata)
    subprocess.run(
        ["docker", "compose", "rm", "--stop", "--force", "weaviate"], check=True
    )
    inspected = subprocess.run(
        ["docker", "volume", "inspect", volume], capture_output=True, text=True
    )
    if inspected.returncode == 0:
        labels = json.loads(inspected.stdout)[0].get("Labels") or {}
        if (
            labels.get("idp-brain.scope") != "local-development"
            or labels.get("idp-brain.disposable") != "true"
        ):
            raise RuntimeError(f"refusing to remove non-disposable volume {volume}")
        subprocess.run(["docker", "volume", "rm", volume], check=True)
    subprocess.run(
        ["docker", "compose", "up", "--wait", "--wait-timeout", "120", "weaviate"],
        check=True,
    )
    subprocess.run(
        ["uv", "run", "python", "-m", "idp_brain.weaviate_admin"], check=True
    )


if __name__ == "__main__":
    main()
