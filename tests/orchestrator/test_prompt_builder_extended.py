"""Testes para funções extraídas do prompt_builder: cache e filtragem de contexto."""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_squad.orchestrator.prompt_builder import (
    _agents_md_cache,
    _workspace_cache,
    build_squad_lead_prompt,
    get_workspace_context_cached,
    read_agents_md_cached,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Limpa caches entre testes."""
    _agents_md_cache.clear()
    _workspace_cache.clear()
    yield
    _agents_md_cache.clear()
    _workspace_cache.clear()


# --- Testes de cache para read_agents_md_cached ---


def test_read_agents_md_cached_retorna_conteudo(tmp_path: Path) -> None:
    """Cache deve retornar conteúdo do AGENTS.md."""
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "po"
    agent_dir.mkdir(parents=True)
    (agent_dir / "AGENTS.md").write_text("# PO Agent", encoding="utf-8")

    result = read_agents_md_cached("po", agents_dir)
    assert result == "# PO Agent"


def test_read_agents_md_cached_usa_cache_na_segunda_chamada(tmp_path: Path) -> None:
    """Segunda chamada dentro do TTL deve usar cache sem I/O."""
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "dev"
    agent_dir.mkdir(parents=True)
    (agent_dir / "AGENTS.md").write_text("original", encoding="utf-8")

    # Primeira chamada popula cache
    result1 = read_agents_md_cached("dev", agents_dir)
    assert result1 == "original"

    # Modifica o arquivo
    (agent_dir / "AGENTS.md").write_text("modified", encoding="utf-8")

    # Segunda chamada dentro do TTL retorna valor cacheado
    result2 = read_agents_md_cached("dev", agents_dir)
    assert result2 == "original"


def test_read_agents_md_cached_expira_apos_ttl(tmp_path: Path, monkeypatch) -> None:
    """Cache deve expirar após TTL e reler o arquivo."""
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "qa"
    agent_dir.mkdir(parents=True)
    (agent_dir / "AGENTS.md").write_text("v1", encoding="utf-8")

    read_agents_md_cached("qa", agents_dir)

    # Avança o relógio além do TTL
    key = f"qa:{agents_dir}"
    content, ts = _agents_md_cache[key]
    _agents_md_cache[key] = (content, ts - 120)

    (agent_dir / "AGENTS.md").write_text("v2", encoding="utf-8")
    result = read_agents_md_cached("qa", agents_dir)
    assert result == "v2"


# --- Testes de cache para get_workspace_context_cached ---


def test_workspace_context_cached_usa_cache() -> None:
    """Deve usar cache na segunda chamada."""
    collector = MagicMock()
    collector.collect.return_value = "contexto do projeto"

    result1 = get_workspace_context_cached(collector, "/workspace")
    assert result1 == "contexto do projeto"
    assert collector.collect.call_count == 1

    result2 = get_workspace_context_cached(collector, "/workspace")
    assert result2 == "contexto do projeto"
    # Não chamou collect novamente (usou cache)
    assert collector.collect.call_count == 1


def test_workspace_context_cached_expira() -> None:
    """Deve recarregar após TTL."""
    collector = MagicMock()
    collector.collect.side_effect = ["v1", "v2"]

    get_workspace_context_cached(collector, "/ws")

    # Expira manualmente
    content, ts = _workspace_cache["/ws"]
    _workspace_cache["/ws"] = (content, ts - 120)

    result = get_workspace_context_cached(collector, "/ws")
    assert result == "v2"


# --- Testes para build_squad_lead_prompt ---


def test_build_prompt_inclui_secoes_basicas() -> None:
    """Prompt deve incluir squad_md, agents_summary e mensagem do usuário."""
    result = build_squad_lead_prompt(
        squad_md="# Squad Lead",
        agents_summary="## Agentes disponiveis",
        running_status="",
        conversation_history="",
        memory_catalog="",
        knowledge_context="",
        pipeline_state="",
        workspace_context="",
        demand_text="Oi, tudo bem?",
        unified_demand_state="",
    )
    assert "# Squad Lead" in result
    assert "## Agentes disponiveis" in result
    assert "<user_message>" in result
    assert "Oi, tudo bem?" in result


def test_build_prompt_filtra_pipeline_vazio() -> None:
    """Não deve incluir seção de pipeline se for 'Nenhuma demanda ativa.'."""
    result = build_squad_lead_prompt(
        squad_md="",
        agents_summary="agentes",
        running_status="",
        conversation_history="",
        memory_catalog="",
        knowledge_context="",
        pipeline_state="Nenhuma demanda ativa.",
        workspace_context="",
        demand_text="teste",
        unified_demand_state="",
    )
    assert "Estado das demandas" not in result


def test_build_prompt_filtra_running_status_vazio() -> None:
    """Não deve incluir seção de agentes se não há agentes ativos."""
    result = build_squad_lead_prompt(
        squad_md="",
        agents_summary="agentes",
        running_status="Nenhum agente ativo no momento.",
        conversation_history="",
        memory_catalog="",
        knowledge_context="",
        pipeline_state="",
        workspace_context="",
        demand_text="teste",
        unified_demand_state="",
    )
    assert "Estado atual dos agentes" not in result


def test_build_prompt_inclui_todas_secoes_quando_preenchidas() -> None:
    """Deve incluir todas as seções quando há conteúdo."""
    result = build_squad_lead_prompt(
        squad_md="# Squad",
        agents_summary="## Agentes",
        running_status="agente X rodando",
        conversation_history="## Historico",
        memory_catalog="## Memória disponível",
        knowledge_context="## Knowledge",
        pipeline_state="## Pipeline step 1",
        workspace_context="contexto ws",
        demand_text="minha demanda",
        unified_demand_state="## Estado das demandas\n\ndemanda ativa",
    )
    assert "Estado atual dos agentes" in result
    assert "Estado das demandas" in result
    assert "## Historico" in result
    assert "## Memória disponível" in result
    assert "## Knowledge" in result
    assert "## Pipeline step 1" in result
    assert "Contexto do Projeto" in result
    assert "Regra de comunicação" in result
    assert "<user_message>" in result


def test_build_prompt_sem_squad_md() -> None:
    """Se squad_md está vazio, não adiciona seção vazia."""
    result = build_squad_lead_prompt(
        squad_md="",
        agents_summary="agentes",
        running_status="",
        conversation_history="",
        memory_catalog="",
        knowledge_context="",
        pipeline_state="",
        workspace_context="",
        demand_text="ola",
        unified_demand_state="",
    )
    # Não deve ter seções vazias consecutivas desnecessárias
    assert result.startswith("agentes")
