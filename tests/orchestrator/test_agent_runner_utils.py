"""Testes para funções utilitárias do agent_runner."""

import asyncio
from unittest.mock import MagicMock

import pytest

from ai_squad.orchestrator.agent_runner import is_transient_not_timeout


class TestIsTransientNotTimeout:
    """Testes para is_transient_not_timeout."""

    def test_timeout_error_nao_retentado(self):
        """asyncio.TimeoutError não é transiente para retry."""
        assert is_transient_not_timeout(asyncio.TimeoutError()) is False

    def test_builtin_timeout_nao_retentado(self):
        """TimeoutError builtin não é transiente para retry."""
        assert is_transient_not_timeout(TimeoutError()) is False

    def test_connection_error_com_padrao_transiente(self):
        """Erro com 'connection' na mensagem é transiente."""
        assert is_transient_not_timeout(ConnectionError("connection reset")) is True

    def test_value_error_nao_retentado(self):
        """ValueError sem padrão transiente não é retentado."""
        assert is_transient_not_timeout(ValueError("bad value")) is False

    def test_overloaded_retentado(self):
        """Erro com 'overloaded' na mensagem é transiente."""
        assert is_transient_not_timeout(RuntimeError("server overloaded")) is True

    def test_rate_limit_retentado(self):
        """Erro com 'rate_limit' na mensagem é transiente."""
        assert is_transient_not_timeout(RuntimeError("rate_limit exceeded")) is True
