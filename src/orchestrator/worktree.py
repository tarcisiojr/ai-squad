"""Gerenciamento de worktrees git por subagente."""

import subprocess
from pathlib import Path


class WorktreeManager:
    """Gerencia worktrees git para isolamento de subagentes.

    Cada subagente recebe seu próprio worktree para trabalhar
    em paralelo sem conflitos.
    """

    def __init__(self, repo_path: str = ".") -> None:
        self._repo_path = Path(repo_path).resolve()
        self._active_worktrees: dict[str, Path] = {}

    def create(self, demand_id: str, agent_name: str, branch: str | None = None) -> Path:
        """Cria worktree para um subagente."""
        worktree_name = f"{demand_id}-{agent_name}"
        worktree_path = self._repo_path / ".worktrees" / worktree_name

        if branch is None:
            branch = f"feature/{worktree_name}"

        cmd = [
            "git", "worktree", "add",
            str(worktree_path),
            "-b", branch,
        ]

        subprocess.run(
            cmd,
            cwd=str(self._repo_path),
            capture_output=True,
            text=True,
            check=True,
        )

        self._active_worktrees[worktree_name] = worktree_path
        return worktree_path

    def remove(self, demand_id: str, agent_name: str) -> None:
        """Remove worktree de um subagente."""
        worktree_name = f"{demand_id}-{agent_name}"
        worktree_path = self._active_worktrees.get(worktree_name)

        if worktree_path is None:
            return

        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path), "--force"],
            cwd=str(self._repo_path),
            capture_output=True,
            text=True,
        )

        self._active_worktrees.pop(worktree_name, None)

    def get_path(self, demand_id: str, agent_name: str) -> Path | None:
        """Retorna caminho do worktree de um subagente."""
        worktree_name = f"{demand_id}-{agent_name}"
        return self._active_worktrees.get(worktree_name)

    def cleanup_demand(self, demand_id: str) -> None:
        """Remove todos os worktrees de uma demanda."""
        to_remove = [
            name for name in self._active_worktrees
            if name.startswith(f"{demand_id}-")
        ]
        for name in to_remove:
            parts = name.split("-", 1)
            if len(parts) == 2:
                self.remove(parts[0], parts[1])

    def list_active(self) -> dict[str, Path]:
        """Retorna worktrees ativos."""
        return dict(self._active_worktrees)
