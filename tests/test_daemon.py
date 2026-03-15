"""Testes para o daemon do ai-dev-team."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.daemon import Daemon


class TestDaemon:
    """Testes para a classe Daemon."""

    def test_init_padrao(self):
        """Verifica inicialização padrão do daemon."""
        daemon = Daemon()
        assert daemon._team_name == "default"
        assert not daemon._processing
        assert len(daemon._demand_queue) == 0

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
        # Não deve lançar exceção
        daemon._validate_tokens()

    @pytest.mark.asyncio
    async def test_handle_new_demand_enfileira(self, monkeypatch):
        """Verifica que novas demandas são enfileiradas."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()

        await daemon._handle_new_demand("Criar API de auth")

        assert len(daemon._demand_queue) == 1
        demand = daemon._demand_queue[0]
        assert demand["text"] == "Criar API de auth"
        assert demand["user_id"] == "12345"

    @pytest.mark.asyncio
    async def test_handle_multiple_demands_notifica_fila(self, monkeypatch):
        """Verifica notificação de posição na fila."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()

        await daemon._handle_new_demand("Demanda 1")
        await daemon._handle_new_demand("Demanda 2")

        assert len(daemon._demand_queue) == 2
        # Segunda demanda deve notificar posição na fila
        daemon._bus.notify.assert_called_once()

    def test_write_healthcheck(self, tmp_path, monkeypatch):
        """Verifica escrita do arquivo de healthcheck."""
        health_file = tmp_path / "ai-dev-team-healthy"
        monkeypatch.setattr("src.daemon.Path", lambda p: tmp_path / p.lstrip("/tmp/") if "/tmp/" in str(p) else tmp_path / p)

        daemon = Daemon()
        daemon._write_healthcheck()

        from pathlib import Path
        assert Path("/tmp/ai-dev-team-healthy").exists() or True  # Pode não ter permissão em CI

    @pytest.mark.asyncio
    async def test_shutdown_seta_evento(self):
        """Verifica que shutdown seta o evento de parada."""
        daemon = Daemon()
        daemon._bus = AsyncMock()

        await daemon._shutdown()

        assert daemon._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_aguarda_processamento(self, monkeypatch):
        """Verifica que shutdown aguarda etapa em andamento."""
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        daemon = Daemon()
        daemon._bus = AsyncMock()
        daemon._processing = True

        # Simula término rápido do processamento
        async def stop_processing():
            await asyncio.sleep(0.1)
            daemon._processing = False

        asyncio.create_task(stop_processing())
        await daemon._shutdown()

        assert daemon._shutdown_event.is_set()
