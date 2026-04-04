"""Testes adicionais para WorkspaceContextCollector — caminhos não cobertos."""

import time

import pytest

from ai_squad.orchestrator.context import WorkspaceContextCollector


class TestCollectBasic:
    """Testes para collect()."""

    def test_workspace_vazio(self, tmp_path):
        """Workspace vazio retorna string vazia."""
        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()
        # Pode ter tree (diretórios vazios)
        assert isinstance(result, str)

    def test_workspace_com_readme(self, tmp_path):
        """Workspace com README.md inclui no contexto."""
        (tmp_path / "README.md").write_text("# Projeto\n\nDescrição", encoding="utf-8")
        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()
        assert "README.md" in result
        assert "Descrição" in result

    def test_workspace_com_claude_md(self, tmp_path):
        """Workspace com CLAUDE.md inclui regras do projeto."""
        (tmp_path / "CLAUDE.md").write_text("# Regras\n\nUse TypeScript", encoding="utf-8")
        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()
        assert "Regras do Projeto" in result
        assert "TypeScript" in result

    def test_workspace_com_agents_md(self, tmp_path):
        """Workspace com AGENTS.md é usado quando CLAUDE.md não existe."""
        (tmp_path / "AGENTS.md").write_text("# Agentes\n\nConfig", encoding="utf-8")
        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect()
        assert "Regras do Projeto" in result

    def test_cache_funciona(self, tmp_path):
        """Segunda chamada usa cache."""
        (tmp_path / "README.md").write_text("# Projeto", encoding="utf-8")
        collector = WorkspaceContextCollector(str(tmp_path))

        result1 = collector.collect()
        # Modifica arquivo — cache deve manter versão antiga
        (tmp_path / "README.md").write_text("# Modificado", encoding="utf-8")
        result2 = collector.collect()

        assert result1 == result2

    def test_cache_expira(self, tmp_path):
        """Cache expira após TTL."""
        (tmp_path / "README.md").write_text("# Projeto", encoding="utf-8")
        collector = WorkspaceContextCollector(str(tmp_path))
        collector.CACHE_TTL = 0  # Expira imediatamente

        result1 = collector.collect()
        (tmp_path / "README.md").write_text("# Modificado", encoding="utf-8")
        result2 = collector.collect()

        assert "Modificado" in result2


class TestReadClaudeMd:
    """Testes para _read_claude_md."""

    def test_claude_md_truncado(self, tmp_path):
        """CLAUDE.md grande é truncado."""
        (tmp_path / "CLAUDE.md").write_text("x" * 10000, encoding="utf-8")
        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector._read_claude_md()
        assert "[truncado]" in result

    def test_sem_claude_nem_agents(self, tmp_path):
        """Sem CLAUDE.md nem AGENTS.md retorna vazio."""
        collector = WorkspaceContextCollector(str(tmp_path))
        assert collector._read_claude_md() == ""


class TestReadSubmoduleAgentsMd:
    """Testes para _read_submodule_agents_md."""

    def test_submodule_com_agents_md(self, tmp_path):
        """Submodule com AGENTS.md retorna conteúdo."""
        sub = tmp_path / "packages" / "api"
        sub.mkdir(parents=True)
        (sub / "AGENTS.md").write_text("# API Config", encoding="utf-8")

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector._read_submodule_agents_md("packages/api")
        assert "Submodulo" in result
        assert "API Config" in result

    def test_submodule_inexistente(self, tmp_path):
        """Submodule inexistente retorna vazio."""
        collector = WorkspaceContextCollector(str(tmp_path))
        assert collector._read_submodule_agents_md("nao/existe") == ""

    def test_submodule_truncado(self, tmp_path):
        """AGENTS.md grande no submodule é truncado."""
        sub = tmp_path / "packages" / "api"
        sub.mkdir(parents=True)
        (sub / "CLAUDE.md").write_text("x" * 10000, encoding="utf-8")

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector._read_submodule_agents_md("packages/api")
        assert "[truncado]" in result

    def test_collect_com_submodule(self, tmp_path):
        """collect() com submodule_path inclui contexto do submodule."""
        sub = tmp_path / "packages" / "api"
        sub.mkdir(parents=True)
        (sub / "AGENTS.md").write_text("# API Config", encoding="utf-8")

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector.collect(submodule_path="packages/api")
        assert "Submodulo" in result


class TestReadReadme:
    """Testes para _read_readme."""

    def test_readme_truncado(self, tmp_path):
        """README.md grande é truncado."""
        (tmp_path / "README.md").write_text("x" * 5000, encoding="utf-8")
        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector._read_readme()
        assert "[truncado]" in result

    def test_sem_readme(self, tmp_path):
        """Sem README.md retorna vazio."""
        collector = WorkspaceContextCollector(str(tmp_path))
        assert collector._read_readme() == ""


class TestReadTree:
    """Testes para _read_tree."""

    def test_tree_com_estrutura(self, tmp_path):
        """Gera árvore de diretórios."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("", encoding="utf-8")
        (tmp_path / "tests").mkdir()

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector._read_tree()
        assert "src/" in result
        assert "main.py" in result
        assert "tests/" in result

    def test_tree_ignora_git(self, tmp_path):
        """Diretórios .git e __pycache__ são ignorados."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "src").mkdir()

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector._read_tree()
        assert ".git" not in result
        assert "__pycache__" not in result
        assert "src/" in result

    def test_tree_workspace_inexistente(self):
        """Workspace inexistente retorna vazio."""
        collector = WorkspaceContextCollector("/nao/existe/path")
        assert collector._read_tree() == ""

    def test_tree_profundidade_limitada(self, tmp_path):
        """Árvore respeita profundidade máxima."""
        # Cria estrutura profunda
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_text("")

        collector = WorkspaceContextCollector(str(tmp_path))
        collector.MAX_TREE_DEPTH = 2
        result = collector._read_tree()
        assert "deep.txt" not in result


class TestReadExistingSpecs:
    """Testes para _read_existing_specs."""

    def test_sem_diretorio_specs(self, tmp_path):
        """Sem diretório specs retorna vazio."""
        collector = WorkspaceContextCollector(str(tmp_path))
        assert collector._read_existing_specs() == ""

    def test_specs_com_proposals(self, tmp_path):
        """Specs com proposals lista demandas."""
        specs = tmp_path / "specs" / "feature-auth"
        specs.mkdir(parents=True)
        (specs / "proposal.md").write_text(
            "# Feature Auth\n\nImplementar autenticação OAuth2",
            encoding="utf-8",
        )

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector._read_existing_specs()
        assert "Demandas anteriores" in result
        assert "feature-auth" in result
        assert "Implementar" in result

    def test_specs_sem_proposal(self, tmp_path):
        """Specs sem proposal.md usa nome do diretório."""
        specs = tmp_path / "specs" / "bugfix-login"
        specs.mkdir(parents=True)

        collector = WorkspaceContextCollector(str(tmp_path))
        result = collector._read_existing_specs()
        assert "bugfix-login" in result

    def test_specs_vazio(self, tmp_path):
        """Diretório specs sem subdiretórios retorna vazio."""
        (tmp_path / "specs").mkdir()
        collector = WorkspaceContextCollector(str(tmp_path))
        assert collector._read_existing_specs() == ""
