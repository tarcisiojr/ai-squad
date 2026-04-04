"""Testes para sessão quente de agente — AgentSession e SessionManager."""

import time

from ai_squad.orchestrator.tools import AgentSession, SessionManager


class TestAgentSession:
    """Testes para dataclass AgentSession."""

    def test_criacao_basica(self) -> None:
        session = AgentSession(
            session_id="dev--d42",
            agent_name="dev",
            demand_id="d42",
        )
        assert session.session_id == "dev--d42"
        assert session.context_loaded is False
        assert session.turn_count == 0
        assert session.ttl == 300

    def test_is_expired_falso_quando_nova(self) -> None:
        session = AgentSession(session_id="dev--d1", agent_name="dev", demand_id="d1")
        assert session.is_expired is False

    def test_is_expired_verdadeiro_apos_ttl(self) -> None:
        session = AgentSession(
            session_id="dev--d1",
            agent_name="dev",
            demand_id="d1",
            ttl=1,
        )
        session.last_active = time.time() - 2  # 2s atrás, TTL é 1s
        assert session.is_expired is True

    def test_touch_atualiza_timestamp_e_turn(self) -> None:
        session = AgentSession(session_id="dev--d1", agent_name="dev", demand_id="d1")
        old_turn = session.turn_count
        session.touch()
        assert session.turn_count == old_turn + 1
        assert session.last_active <= time.time()


class TestSessionManager:
    """Testes para gerenciador de sessões."""

    def test_get_or_create_nova(self) -> None:
        mgr = SessionManager()
        session, is_new = mgr.get_or_create("dev", "d42")
        assert is_new is True
        assert session.agent_name == "dev"
        assert session.demand_id == "d42"
        assert session.session_id == "dev--d42"

    def test_get_or_create_reutiliza(self) -> None:
        mgr = SessionManager()
        s1, new1 = mgr.get_or_create("dev", "d42")
        s1.context_loaded = True

        s2, new2 = mgr.get_or_create("dev", "d42")
        assert new2 is False
        assert s2.context_loaded is True  # mesma sessão
        assert s2.turn_count == 1  # touch incrementou

    def test_get_or_create_recria_apos_ttl(self) -> None:
        mgr = SessionManager()
        s1, _ = mgr.get_or_create("dev", "d42")
        s1.context_loaded = True
        s1.ttl = 0  # expira imediatamente
        s1.last_active = time.time() - 1

        s2, new2 = mgr.get_or_create("dev", "d42")
        assert new2 is True
        assert s2.context_loaded is False  # sessão nova

    def test_invalidate_remove_sessao(self) -> None:
        mgr = SessionManager()
        mgr.get_or_create("dev", "d42")
        assert mgr.active_count == 1

        mgr.invalidate("dev", "d42")
        assert mgr.active_count == 0

    def test_invalidate_demand_remove_todas(self) -> None:
        mgr = SessionManager()
        mgr.get_or_create("dev", "d42")
        mgr.get_or_create("qa", "d42")
        mgr.get_or_create("dev", "d99")  # outra demanda
        assert mgr.active_count == 3

        mgr.invalidate_demand("d42")
        assert mgr.active_count == 1  # só d99 resta

    def test_cleanup_expired(self) -> None:
        mgr = SessionManager()
        s1, _ = mgr.get_or_create("dev", "d1")
        s1.ttl = 0
        s1.last_active = time.time() - 1  # expirada

        mgr.get_or_create("qa", "d2")  # ativa

        removed = mgr.cleanup_expired()
        assert removed == 1
        assert mgr.active_count == 1

    def test_agentes_diferentes_mesma_demanda(self) -> None:
        """Agentes diferentes na mesma demanda têm sessões separadas."""
        mgr = SessionManager()
        s1, _ = mgr.get_or_create("dev", "d42")
        s2, _ = mgr.get_or_create("qa", "d42")
        assert s1.session_id != s2.session_id
        assert mgr.active_count == 2
