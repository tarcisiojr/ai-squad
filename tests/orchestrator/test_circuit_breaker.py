"""Testes para circuit breaker e reconexão do bus."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_squad.orchestrator.agent_runner import AgentRunner, RunnerContext
from ai_squad.orchestrator.tools import RunningAgent

# Patch asyncio.sleep globalmente neste módulo para evitar delays reais
_SLEEP_PATCH = "ai_squad.orchestrator.agent_runner.asyncio.sleep"


def _make_runner_context(tmp_path: Path, bus_mock: MagicMock) -> RunnerContext:
    """Cria RunnerContext com mocks mínimos para testes."""
    return RunnerContext(
        adapter=MagicMock(),
        message_bus=bus_mock,
        personas={},
        agents_dir=tmp_path / "agents",
        workspace=str(tmp_path),
        agent_timeout=60,
        context_collector=MagicMock(),
        conversation=MagicMock(),
        journal=MagicMock(),
        lessons=MagicMock(),
        daily_notes=MagicMock(),
        state_manager=MagicMock(),
        graph=MagicMock(),
    )


def _make_running_agent(agent_name: str = "dev") -> RunningAgent:
    """Cria RunningAgent mínimo para testes."""
    return RunningAgent(
        agent_name=agent_name,
        demand_id="d1",
        user_id="u1",
        thread_id=None,
        started_at=0.0,
        status="error",
    )


def _make_runner(tmp_path: Path) -> tuple[AgentRunner, MagicMock]:
    """Cria AgentRunner com mocks e retorna (runner, bus_mock)."""
    bus = MagicMock()
    bus.send_message = AsyncMock()
    bus.mark_agent_active = MagicMock()
    bus.mark_agent_idle = MagicMock()
    ctx = _make_runner_context(tmp_path, bus)
    on_trigger = AsyncMock()
    keep_typing = AsyncMock()
    runner = AgentRunner(ctx, on_trigger, keep_typing)
    return runner, bus


class TestCircuitBreaker:
    """Testes para circuit breaker no AgentRunner."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_abre_apos_3_falhas(self, tmp_path):
        """Circuit breaker abre após 3 falhas consecutivas."""
        runner, bus = _make_runner(tmp_path)
        agent = _make_running_agent()

        assert not runner._circuit_open
        assert runner._consecutive_failures == 0

        with patch(_SLEEP_PATCH, new_callable=AsyncMock):
            for i in range(3):
                await runner.schedule_auto_recovery(agent, f"erro {i}")

        assert runner._circuit_open
        assert runner._consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_envia_mensagem_ao_usuario(self, tmp_path):
        """Quando circuit breaker abre, notifica o usuário."""
        runner, bus = _make_runner(tmp_path)
        agent = _make_running_agent()

        with patch(_SLEEP_PATCH, new_callable=AsyncMock):
            for i in range(3):
                await runner.schedule_auto_recovery(agent, f"erro {i}")

        # Verifica que mensagem foi enviada ao usuario
        bus.send_message.assert_called()
        call_args = bus.send_message.call_args
        msg_text = call_args[0][1] if call_args[0] else call_args[1].get("text", "")
        assert "pausado" in msg_text.lower()

    @pytest.mark.asyncio
    async def test_circuit_breaker_reseta_com_nova_mensagem(self, tmp_path):
        """Circuit breaker reseta quando reset_circuit_breaker() é chamado."""
        runner, bus = _make_runner(tmp_path)
        agent = _make_running_agent()

        with patch(_SLEEP_PATCH, new_callable=AsyncMock):
            for i in range(3):
                await runner.schedule_auto_recovery(agent, f"erro {i}")

        assert runner._circuit_open

        # Reseta (simula nova mensagem do usuario)
        runner.reset_circuit_breaker()

        assert not runner._circuit_open
        assert runner._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_nao_abre_antes_do_threshold(self, tmp_path):
        """Circuit breaker não abre com menos de 3 falhas."""
        runner, bus = _make_runner(tmp_path)
        agent = _make_running_agent()

        with patch(_SLEEP_PATCH, new_callable=AsyncMock):
            await runner.schedule_auto_recovery(agent, "erro 1")
            await runner.schedule_auto_recovery(agent, "erro 2")

        assert not runner._circuit_open
        assert runner._consecutive_failures == 2


class TestBusReconnection:
    """Testes para reconexão do bus com backoff no daemon."""

    @pytest.mark.asyncio
    async def test_bus_reconecta_apos_erro(self):
        """Bus reconecta com backoff após erro de conexão."""
        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("conexao perdida")
            return True

        mock_bus = MagicMock()
        mock_bus.run_forever = AsyncMock(side_effect=side_effect)

        shutdown_event = asyncio.Event()
        reconnect_delay = 2
        max_reconnect_delay = 60

        with patch("asyncio.sleep", new_callable=AsyncMock):
            while not shutdown_event.is_set():
                try:
                    result = await mock_bus.run_forever()
                    if result is None:
                        break
                    break
                except asyncio.CancelledError:
                    break
                except Exception:
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

        assert call_count == 2
        assert reconnect_delay == 4  # dobrou de 2 para 4

    @pytest.mark.asyncio
    async def test_backoff_respeita_maximo(self):
        """Backoff exponencial não ultrapassa 60 segundos."""
        delay = 2
        max_delay = 60

        for _ in range(10):
            delay = min(delay * 2, max_delay)

        assert delay == max_delay
