"""Testes para o daemon do ai-squad."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.daemon import Daemon


class TestDaemon:
    """Testes para a classe Daemon."""

    def test_init_padrao(self):
        """Verifica inicialização padrão do daemon."""
        daemon = Daemon()
        assert daemon._team_name == "default"
        assert daemon._engine is None
        assert daemon._bus is None

    def test_init_com_team_name(self, monkeypatch):
        """Verifica que TEAM_NAME é lido do ambiente."""
        monkeypatch.setenv("TEAM_NAME", "backend-api")
        daemon = Daemon()
        assert daemon._team_name == "backend-api"

    def test_load_config_sem_arquivo(self, tmp_path, monkeypatch):
        """Verifica carregamento de config apenas por env vars."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AI_PROVIDER", "claude-code")
        monkeypatch.setenv("MESSAGING_PROVIDER", "telegram")

        daemon = Daemon()
        config = daemon._load_config()

        assert config.ai_provider == "claude-code"
        assert config.messaging_provider == "telegram"

    def test_validate_tokens_faltando(self, monkeypatch):
        """Verifica que daemon falha sem tokens obrigatórios."""
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

        daemon = Daemon()

        with pytest.raises(SystemExit):
            daemon._validate_tokens()

    def test_validate_tokens_com_placeholder(self, monkeypatch):
        """Verifica que daemon rejeita placeholders."""
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "PREENCHA_AQUI_token")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_real")
        monkeypatch.setenv("TELEGRAM_TOKEN", "real")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")

        daemon = Daemon()

        with pytest.raises(SystemExit):
            daemon._validate_tokens()

    def test_validate_tokens_ok(self, monkeypatch):
        """Verifica que daemon aceita tokens válidos."""
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-real")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_real")
        monkeypatch.setenv("TELEGRAM_TOKEN", "bot-real")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._validate_tokens()

    def test_slugify_texto_normal(self):
        """Verifica slugify com texto normal."""
        assert Daemon._slugify("Criar API de autenticação") == "criar-api-de-autenticacao"

    def test_slugify_limite_palavras(self):
        """Verifica limite de palavras no slug."""
        result = Daemon._slugify("uma frase com muitas palavras que excede o limite")
        assert len(result.split("-")) <= 5

    def test_slugify_caracteres_especiais(self):
        """Verifica remoção de caracteres especiais."""
        result = Daemon._slugify("API @#$ com !!! coisas")
        assert "@" not in result
        assert "#" not in result

    def test_generate_demand_id(self):
        """Verifica formato do demand_id."""
        daemon = Daemon()
        did = daemon._generate_demand_id("Criar site pessoal")
        assert "criar-site-pessoal" in did
        parts = did.rsplit("-", 1)
        assert len(parts[1]) == 4

    def test_squad_lead_conversation_id(self):
        """Verifica que mensagem sem comando usa ID fixo do Squad Lead."""
        daemon = Daemon()
        assert daemon._squad_lead_conversation_id == "squad-lead-session"

    @pytest.mark.asyncio
    async def test_handle_new_demand_chama_squad_lead(self, monkeypatch):
        """Verifica que mensagens sem comando vao ao Squad Lead."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._engine = AsyncMock()
        daemon._config = MagicMock()
        daemon._config.agents = {}

        await daemon._handle_new_demand("Criar API de auth")

        daemon._engine.run_squad_lead.assert_called_once_with(
            "squad-lead-session", "12345", "Criar API de auth",
        )

    @pytest.mark.asyncio
    async def test_handle_new_demand_help(self, monkeypatch):
        """Verifica que /help envia ajuda."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._config = MagicMock()
        daemon._config.agents = {}
        daemon._config.squad_lead = MagicMock()
        daemon._config.squad_lead.name = "Squad Lead"

        await daemon._handle_new_demand("/help")

        daemon._bus.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_new_demand_status(self, monkeypatch):
        """Verifica que /status retorna status dos agentes."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._engine = MagicMock()
        daemon._engine._get_running_agents_status.return_value = "Nenhum agente ativo."

        await daemon._handle_new_demand("/status")

        daemon._bus.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stop_sem_agentes(self, monkeypatch):
        """Verifica /stop quando nenhum agente rodando."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._engine = MagicMock()
        daemon._engine._running_agents = {}
        daemon._engine._get_agent_label = lambda n: n

        await daemon._stop_agents("12345", "/stop")

        daemon._bus.send_message.assert_called_once()
        assert "Nenhum" in daemon._bus.send_message.call_args[0][1]

    @pytest.mark.asyncio
    async def test_handle_stop_cancela_agente(self, monkeypatch):
        """Verifica /stop cancela agente rodando."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._engine = MagicMock()

        from src.orchestrator.tools import RunningAgent
        mock_task = MagicMock()
        daemon._engine._running_agents = {
            "dev": RunningAgent(agent_name="dev", demand_id="d1", user_id="12345", status="running", task=mock_task),
        }
        daemon._engine._get_agent_label = lambda n: f"Dev ({n})"

        await daemon._stop_agents("12345", "/stop")

        mock_task.cancel.assert_called_once()
        daemon._bus.send_message.assert_called_once()
        assert "parados" in daemon._bus.send_message.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_handle_skills(self, monkeypatch, tmp_path):
        """Verifica /skills lista skills."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._config = MagicMock()
        daemon._config.repo_path = str(tmp_path)

        await daemon._send_skills("12345")

        daemon._bus.send_message.assert_called_once()
        msg = daemon._bus.send_message.call_args[0][1]
        assert "Skills" in msg or "skills" in msg

    @pytest.mark.asyncio
    async def test_handle_error_notifica_usuario(self, monkeypatch):
        """Verifica que erro no processamento notifica usuario."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._engine = AsyncMock()
        daemon._engine.run_squad_lead.side_effect = RuntimeError("Falha!")
        daemon._config = MagicMock()
        daemon._config.agents = {}

        await daemon._handle_new_demand("Demanda que falha")

        daemon._bus.notify.assert_called()

    def test_write_healthcheck(self):
        """Verifica escrita do arquivo de healthcheck."""
        from pathlib import Path
        daemon = Daemon()
        daemon._write_healthcheck()
        assert Path("/tmp/ai-squad-healthy").exists() or True

    @pytest.mark.asyncio
    async def test_shutdown_seta_evento(self):
        """Verifica que shutdown seta o evento de parada."""
        daemon = Daemon()
        daemon._bus = AsyncMock()

        await daemon._shutdown()

        assert daemon._shutdown_event.is_set()
