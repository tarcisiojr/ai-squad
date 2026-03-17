"""Testes para gerenciamento de worktrees git."""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from src.orchestrator.worktree import WorktreeManager


class TestWorktreeManager:
    """Testes para WorktreeManager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Cria instância de WorktreeManager."""
        return WorktreeManager(repo_path=str(tmp_path))

    def test_create_worktree(self, manager):
        """Verifica criação de worktree."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            path = manager.create("demand-1", "dev-web")

        assert "demand-1-dev-web" in str(path)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "worktree" in cmd
        assert "add" in cmd

    def test_create_worktree_com_branch(self, manager):
        """Verifica criação de worktree com branch específica."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            manager.create("demand-1", "dev-web", branch="fix/bug-123")

        cmd = mock_run.call_args[0][0]
        assert "fix/bug-123" in cmd

    def test_remove_worktree(self, manager):
        """Verifica remoção de worktree."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            manager.create("demand-1", "dev-web")
            manager.remove("demand-1", "dev-web")

        assert manager.get_path("demand-1", "dev-web") is None

    def test_remove_worktree_inexistente(self, manager):
        """Verifica que remover worktree inexistente não falha."""
        manager.remove("inexistente", "agent")

    def test_get_path(self, manager):
        """Verifica obtenção de caminho do worktree."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            expected = manager.create("demand-1", "dev-web")

        path = manager.get_path("demand-1", "dev-web")
        assert path == expected

    def test_get_path_inexistente(self, manager):
        """Verifica que retorna None para worktree inexistente."""
        assert manager.get_path("inexistente", "agent") is None

    def test_cleanup_demand(self, manager):
        """Verifica limpeza de worktrees de uma demanda."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            manager.create("demand-1", "dev-web")
            manager.create("demand-1", "qa")
            manager.create("demand-2", "dev-web")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            manager.cleanup_demand("demand-1")

        # Worktrees da demand-1 removidos
        assert manager.get_path("demand-1", "dev-web") is None
        assert manager.get_path("demand-1", "qa") is None
        # Worktree da demand-2 mantido
        assert manager.get_path("demand-2", "dev-web") is not None

    def test_list_active(self, manager):
        """Verifica listagem de worktrees ativos."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            manager.create("demand-1", "dev-web")
            manager.create("demand-2", "qa")

        active = manager.list_active()
        assert len(active) == 2
        assert "demand-1-dev-web" in active
        assert "demand-2-qa" in active
