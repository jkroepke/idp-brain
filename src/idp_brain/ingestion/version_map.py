"""Evidence-backed version labels for Git ingestion snapshots."""

from __future__ import annotations


def git_version_label(*, ref_label: str, commit_sha: str, ref_type: str) -> str:
    """Return a stable, human-readable label for one resolved Git ref."""

    safe_ref = ref_label.replace("refs/heads/", "").replace("refs/tags/", "")
    prefix = (
        "tag" if ref_type == "tag" else "branch" if ref_type == "branch" else "commit"
    )
    return f"{prefix}:{safe_ref}@{commit_sha[:12]}"
