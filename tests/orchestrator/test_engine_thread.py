"""Testes para propagação de thread_id no engine."""

from unittest.mock import MagicMock

from ai_squad.orchestrator.tools import RunningAgent


class TestRunningAgentThreadId:
    """Testes para thread_id no RunningAgent."""

    def test_thread_id_default_none(self):
        """RunningAgent sem thread_id definido."""
        ra = RunningAgent(agent_name="po", demand_id="login-a1b2")
        assert ra.thread_id is None

    def test_thread_id_definido(self):
        """RunningAgent com thread_id."""
        ra = RunningAgent(
            agent_name="po",
            demand_id="login-a1b2",
            thread_id=123,
        )
        assert ra.thread_id == 123

    def test_thread_id_preservado(self):
        """Thread_id é preservado ao atualizar status."""
        ra = RunningAgent(
            agent_name="dev",
            demand_id="dash-z3",
            thread_id=456,
        )
        ra.status = "done"
        ra.result = "implementado"
        assert ra.thread_id == 456


class TestEngineResolveThreadId:
    """Testes para resolução de thread_id no engine."""

    def test_resolve_thread_id_de_running_agent(self):
        """Resolve thread_id direto do RunningAgent."""
        from ai_squad.orchestrator.engine import OrchestrationEngine

        engine = MagicMock(spec=OrchestrationEngine)
        engine._running_agents = {
            "po": RunningAgent(
                agent_name="po",
                demand_id="login",
                thread_id=123,
            ),
        }
        engine._default_thread_id = None
        engine._thread_map = None

        # Chama o método real
        result = OrchestrationEngine._resolve_thread_id(engine, "po")
        assert result == 123

    def test_resolve_thread_id_fallback_default(self):
        """Sem agente, usa default_thread_id."""
        from ai_squad.orchestrator.engine import OrchestrationEngine

        engine = MagicMock(spec=OrchestrationEngine)
        engine._running_agents = {}
        engine._default_thread_id = 999
        engine._thread_map = None

        result = OrchestrationEngine._resolve_thread_id(engine, "")
        assert result == 999

    def test_resolve_thread_id_via_thread_map(self):
        """Resolve via thread_map quando RunningAgent não tem thread_id."""
        from ai_squad.orchestrator.engine import OrchestrationEngine

        mock_map = MagicMock()
        mock_map.get_thread.return_value = 789

        engine = MagicMock(spec=OrchestrationEngine)
        engine._running_agents = {
            "dev": RunningAgent(agent_name="dev", demand_id="dash-z3"),
        }
        engine._default_thread_id = None
        engine._thread_map = mock_map

        result = OrchestrationEngine._resolve_thread_id(engine, "dev")
        assert result == 789
        mock_map.get_thread.assert_called_once_with("dash-z3")
