"""Testes para roteamento de Forum Topics no daemon."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.daemon import Daemon


class TestDaemonForumRouting:
    """Testes para roteamento de mensagens via Forum Topics."""

    @pytest.fixture
    def daemon(self, monkeypatch):
        """Cria daemon com mocks básicos."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "grupo-999")
        d = Daemon()
        d._engine = MagicMock()
        d._engine.run_squad_lead = AsyncMock(return_value="ok")
        d._bus = MagicMock()
        d._bus.send_message = AsyncMock()
        d._bus.notify = AsyncMock()
        d._bus.create_thread = AsyncMock(return_value=42)
        return d

    @pytest.mark.asyncio
    async def test_mensagem_topico_mapeado_roteia_para_demand(self, daemon):
        """Mensagem em tópico mapeado usa demand_id correspondente."""
        from src.orchestrator.thread_map import ThreadDemandMap

        daemon._thread_map = ThreadDemandMap(state_dir="/tmp/test-state-forum")
        daemon._thread_map.add(123, "login-oauth-a1b2")

        await daemon._handle_new_demand(
            "Como está o progresso?",
            thread_id=123,
            user_id="111",
        )

        daemon._engine.run_squad_lead.assert_called_once()
        call_kwargs = daemon._engine.run_squad_lead.call_args
        assert call_kwargs[0][0] == "login-oauth-a1b2"  # demand_id
        assert call_kwargs[1]["thread_id"] == 123

    @pytest.mark.asyncio
    async def test_mensagem_topico_geral_usa_sessao_geral(self, daemon):
        """Mensagem sem thread_id vai para Squad Lead sessão geral."""
        from src.orchestrator.thread_map import ThreadDemandMap

        daemon._thread_map = ThreadDemandMap(state_dir="/tmp/test-state-forum2")

        await daemon._handle_new_demand(
            "Olá, quero criar algo",
            thread_id=None,
            user_id="111",
        )

        daemon._engine.run_squad_lead.assert_called_once()
        call_kwargs = daemon._engine.run_squad_lead.call_args
        assert call_kwargs[0][0] == "squad-lead-session"

    @pytest.mark.asyncio
    async def test_mensagem_topico_desconhecido_mapeia_automaticamente(self, daemon):
        """Mensagem em tópico sem mapeamento cria demand_id e mapeia."""
        from src.orchestrator.thread_map import ThreadDemandMap

        daemon._thread_map = ThreadDemandMap(state_dir="/tmp/test-state-forum3")

        await daemon._handle_new_demand(
            "Pergunta genérica",
            thread_id=999,
            user_id="111",
        )

        daemon._engine.run_squad_lead.assert_called_once()
        call_kwargs = daemon._engine.run_squad_lead.call_args
        # Deve ter criado demand_id (não "squad-lead-session")
        assert call_kwargs[0][0] != "squad-lead-session"
        assert call_kwargs[1]["thread_id"] == 999
        # Mapeamento deve existir
        assert daemon._thread_map.get_demand(999) is not None

    @pytest.mark.asyncio
    async def test_dm_sem_thread_preserva_comportamento(self, daemon):
        """DM sem thread_id funciona como antes (fallback modo flat)."""
        await daemon._handle_new_demand("Olá")

        daemon._engine.run_squad_lead.assert_called_once()
        call_kwargs = daemon._engine.run_squad_lead.call_args
        assert call_kwargs[0][0] == "squad-lead-session"


class TestDaemonForumDetection:
    """Testes para detecção de modo fórum."""

    def test_is_forum_default_false(self):
        """Por padrão, is_forum é False."""
        daemon = Daemon()
        assert daemon._is_forum is False

    def test_thread_map_inicializado_none(self):
        """Thread map começa como None antes de setup."""
        daemon = Daemon()
        assert daemon._thread_map is None
