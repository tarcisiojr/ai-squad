"""Testes para o coletor de contexto do workspace."""

from src.orchestrator.context import WorkspaceContextCollector


class TestWorkspaceContextCollector:
    """Testes para WorkspaceContextCollector."""

    def test_collect_com_readme(self, tmp_path):
        """Verifica coleta de README.md."""
        (tmp_path / "README.md").write_text("# Meu Projeto\nDescrição aqui.")
        collector = WorkspaceContextCollector(str(tmp_path))

        result = collector.collect()

        assert "### README.md" in result
        assert "Meu Projeto" in result

    def test_collect_sem_readme(self, tmp_path):
        """Verifica comportamento sem README."""
        collector = WorkspaceContextCollector(str(tmp_path))

        result = collector.collect()

        assert "README" not in result

    def test_readme_truncamento(self, tmp_path):
        """Verifica truncamento de README grande."""
        (tmp_path / "README.md").write_text("x" * 5000)
        collector = WorkspaceContextCollector(str(tmp_path))

        result = collector.collect()

        assert "[truncado]" in result

    def test_tree_basica(self, tmp_path):
        """Verifica geração de árvore de diretórios."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").touch()
        (tmp_path / "tests").mkdir()

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()

        assert "src/" in result
        assert "main.py" in result
        assert "tests/" in result

    def test_tree_ignora_git(self, tmp_path):
        """Verifica que .git é ignorado."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "src").mkdir()

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()

        assert ".git" not in result
        assert "src/" in result

    def test_tree_profundidade_limitada(self, tmp_path):
        """Verifica limite de profundidade da árvore."""
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "deep.txt").touch()

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()

        # Profundidade 3+ não deve aparecer
        assert "deep.txt" not in result

    def test_specs_existentes(self, tmp_path):
        """Verifica leitura de specs anteriores."""
        specs_dir = tmp_path / "specs" / "demand-001"
        specs_dir.mkdir(parents=True)
        (specs_dir / "proposal.md").write_text("# Demanda\nCriar API de auth.")

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()

        assert "Demandas anteriores" in result
        assert "demand-001" in result

    def test_sem_specs(self, tmp_path):
        """Verifica comportamento sem pasta specs."""
        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()

        assert "Demandas anteriores" not in result

    def test_workspace_vazio(self, tmp_path):
        """Verifica comportamento com workspace vazio."""
        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()

        # Pode ter tree mas sem README nem specs
        assert "README" not in result
