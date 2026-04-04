"""Testes complementares para AIAgentAdapter — apenas testes únicos não cobertos em test_claude_agent_sdk.py."""

from unittest.mock import AsyncMock

import pytest

from ai_squad.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter


class TestClaudeAgentSDKAdapterExtras:
    """Testes complementares que não existem em test_claude_agent_sdk.py."""

    @pytest.fixture
    def adapter(self):
        """Cria instância de ClaudeAgentSDKAdapter."""
        return ClaudeAgentSDKAdapter(timeout=30)

    def test_build_prompt_com_workspace_context(self, adapter):
        """Verifica montagem do prompt com contexto do workspace."""
        prompt = adapter._build_prompt(
            "Crie um teste",
            {"workspace_context": "README conteudo aqui"},
        )
        assert "## Contexto do Projeto" in prompt
        assert "README conteudo aqui" in prompt

    def test_build_prompt_com_system_instructions(self, adapter):
        """Verifica montagem do prompt com instruções do sistema."""
        prompt = adapter._build_prompt(
            "Crie um teste",
            {"system_instructions": "Voce e o PO."},
        )
        assert "Voce e o PO." in prompt

    def test_set_callbacks(self, adapter):
        """Verifica que callbacks são configuráveis via on()."""
        from ai_squad.common.events import EVENT_GET_AGENTS, EVENT_PROGRESS, EVENT_START_AGENT

        cb1 = AsyncMock()
        cb2 = AsyncMock()
        cb3 = AsyncMock()

        adapter.on(EVENT_PROGRESS, cb1)
        adapter.on(EVENT_START_AGENT, cb2)
        adapter.on(EVENT_GET_AGENTS, cb3)

        assert adapter._callbacks.has(EVENT_PROGRESS)
        assert adapter._callbacks.has(EVENT_START_AGENT)
        assert adapter._callbacks.has(EVENT_GET_AGENTS)

    def test_session_management(self, adapter):
        """Verifica gerenciamento de sessões."""
        assert adapter.get_session_id("conv-1") is None

        adapter._sessions["conv-1"] = "session-abc"
        assert adapter.get_session_id("conv-1") == "session-abc"

        adapter.clear_session("conv-1")
        assert adapter.get_session_id("conv-1") is None
