"""Small Git CLI wrapper for ingestion fetchers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GitCommandError(RuntimeError):
    """Raised when a Git command fails without exposing credentials."""

    def __init__(self, *, command: tuple[str, ...], returncode: int) -> None:
        super().__init__(command)
        self.command = command
        self.returncode = returncode

    def __str__(self) -> str:
        return f"git command failed with exit code {self.returncode}"


class GitClient:
    """Run Git commands with bounded, non-interactive defaults."""

    def run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> str:
        env = os.environ.copy()
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and result.returncode != 0:
            raise GitCommandError(
                command=tuple(["git", *args]),
                returncode=result.returncode,
            )
        return result.stdout.strip()
