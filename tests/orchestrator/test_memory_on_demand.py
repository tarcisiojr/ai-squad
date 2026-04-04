"""Testes para memória on-demand: catálogo, query tools e deduplicação."""

from pathlib import Path

import pytest

from ai_squad.orchestrator.daily_notes import DailyNotes
from ai_squad.orchestrator.journal import JournalStore
from ai_squad.orchestrator.lessons import LessonsStore
from ai_squad.orchestrator.prompt_builder import (
    build_memory_catalog,
    build_squad_lead_prompt,
    build_unified_demand_state,
)


@pytest.fixture()
def stores(tmp_path: Path) -> tuple[LessonsStore, JournalStore, DailyNotes]:
    """Cria stores em diretório temporário."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    lessons = LessonsStore(state_dir=state_dir)
    journal = JournalStore(state_dir=state_dir)
    daily = DailyNotes(state_dir=state_dir)
    return lessons, journal, daily


class TestBuildMemoryCatalog:
    """Testes para catálogo mínimo de memória."""

    def test_catalogo_com_licoes(
        self, stores: tuple[LessonsStore, JournalStore, DailyNotes]
    ) -> None:
        lessons, journal, daily = stores
        lessons.add("bug", "Timeout no banco", "Aumentar timeout para 30s")
        lessons.add("processo", "Deploy sexta", "Evitar deploy sexta")

        result = build_memory_catalog(lessons, journal, daily)
        assert "Lições" in result
        assert "(2)" in result
        assert "query_lessons" in result

    def test_catalogo_com_journal(
        self, stores: tuple[LessonsStore, JournalStore, DailyNotes]
    ) -> None:
        lessons, journal, daily = stores
        journal.create("d42", "Implementar auth")
        journal.set_phase("d42", "dev_working")  # Precisa estar ativo (não idle)

        result = build_memory_catalog(lessons, journal, daily)
        assert "Journal" in result
        assert "#d42" in result
        assert "query_journal" in result

    def test_catalogo_com_notas(
        self, stores: tuple[LessonsStore, JournalStore, DailyNotes]
    ) -> None:
        lessons, journal, daily = stores
        daily.add_entry("Teste de notas")

        result = build_memory_catalog(lessons, journal, daily)
        assert "Notas" in result
        assert "query_daily_notes" in result

    def test_catalogo_vazio_sem_dados(
        self, stores: tuple[LessonsStore, JournalStore, DailyNotes]
    ) -> None:
        lessons, journal, daily = stores
        result = build_memory_catalog(lessons, journal, daily)
        assert result == ""

    def test_catalogo_compacto(
        self, stores: tuple[LessonsStore, JournalStore, DailyNotes]
    ) -> None:
        """Catálogo deve ser compacto (< 500 tokens estimados)."""
        lessons, journal, daily = stores
        for i in range(10):
            lessons.add(f"cat{i}", f"Problema {i}", f"Solução {i}")
        journal.create("d1", "Demanda 1")
        journal.create("d2", "Demanda 2")
        daily.add_entry("Nota do dia")

        result = build_memory_catalog(lessons, journal, daily)
        estimated_tokens = len(result) // 3
        assert estimated_tokens < 500


class TestBuildUnifiedDemandState:
    """Testes para seção unificada de estado."""

    def test_sem_demandas_retorna_vazio(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        journal = JournalStore(state_dir=state_dir)
        from ai_squad.orchestrator.state import StateManager

        state_mgr = StateManager(state_dir=state_dir)

        result = build_unified_demand_state(journal, state_mgr, {}, {})
        assert result == ""

    def test_inclui_decisoes_recentes(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        journal = JournalStore(state_dir=state_dir)
        journal.create("d42", "Implementar auth")
        journal.set_phase("d42", "dev_working")
        journal.add_decision("d42", "delegou_dev", "Delegou ao dev-backend")
        journal.add_decision("d42", "escolha_jwt", "Escolheu JWT sobre sessions")
        from ai_squad.orchestrator.state import StateManager

        state_mgr = StateManager(state_dir=state_dir)

        result = build_unified_demand_state(journal, state_mgr, {}, {})
        assert "Estado das demandas" in result
        assert "d42" in result
        assert "dev_working" in result
        assert "delegou_dev" in result
        assert "escolha_jwt" in result


class TestDeduplicacao:
    """Testes para verificar que a deduplicação funciona."""

    def test_prompt_sem_journal_separado(self) -> None:
        """Prompt do Squad Lead não deve ter seção separada de journal."""
        result = build_squad_lead_prompt(
            squad_md="# Squad Lead",
            agents_summary="## Agentes",
            running_status="",
            conversation_history="",
            memory_catalog="## Memória disponível",
            knowledge_context="",
            pipeline_state="",
            workspace_context="",
            demand_text="ola",
            unified_demand_state="## Estado das demandas\n\ndemanda ativa",
        )
        assert "Historico de decisoes (Journal)" not in result
        assert "Estado das demandas" in result

    def test_prompt_usa_catalogo_em_vez_de_lessons(self) -> None:
        """Prompt deve usar catálogo de memória, não lessons completas."""
        result = build_squad_lead_prompt(
            squad_md="",
            agents_summary="agentes",
            running_status="",
            conversation_history="",
            memory_catalog="## Memória disponível\n- Lições (5): temas: bug, deploy",
            knowledge_context="",
            pipeline_state="",
            workspace_context="",
            demand_text="teste",
            unified_demand_state="",
        )
        assert "Memória disponível" in result
        assert "query_lessons" not in result or "Lições" in result


class TestEngineContextBudgetIntegration:
    """Teste de integração: engine + ContextBudget produz prompt dentro do budget."""

    def test_prompt_squad_lead_dentro_do_budget(self, tmp_path: Path) -> None:
        """Prompt do Squad Lead deve ser razoavelmente compacto após otimizações."""
        from ai_squad.adapters.interface import AIAgentAdapter
        from ai_squad.models import AgentStatus
        from ai_squad.orchestrator.context_budget import ContextBudget
        from ai_squad.orchestrator.engine import OrchestrationEngine
        from ai_squad.orchestrator.state import StateManager

        class MockAdapter(AIAgentAdapter):
            async def run(self, prompt: str, context: dict) -> str:  # type: ignore[override]
                return "ok"

            async def ask(self, question: str) -> str:
                return "ok"

            def status(self) -> AgentStatus:
                return AgentStatus.IDLE

            def on_human_needed(self, callback: object) -> None:
                pass

        class MockBus:
            default_chat_id = "123"
            supports_threads = False

            async def send_message(self, *a: object, **kw: object) -> None:
                pass

            async def send_typing(self, *a: object, **kw: object) -> None:
                pass

            async def notify(self, *a: object, **kw: object) -> None:
                pass

            async def ask_user(self, *a: object, **kw: object) -> str:
                return "ok"

            async def send_approval_request(self, *a: object, **kw: object) -> str:
                return "ok"

            async def send_photo(self, *a: object, **kw: object) -> None:
                pass

            def register_personas(self, *a: object) -> None:
                pass

            def mark_agent_active(self, *a: object) -> None:
                pass

            def mark_agent_idle(self, *a: object) -> None:
                pass

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Cria AGENTS.md do squad-lead
        sl_dir = agents_dir / "squad-lead"
        sl_dir.mkdir()
        (sl_dir / "AGENTS.md").write_text("# Squad Lead\nVocê coordena o time.", encoding="utf-8")

        engine = OrchestrationEngine(
            adapter=MockAdapter(),
            message_bus=MockBus(),  # type: ignore[arg-type]
            state_manager=StateManager(state_dir=str(state_dir)),
            workspace=str(tmp_path),
            agents_dir=str(agents_dir),
            personas={},
        )

        # Popula dados para simular cenário real
        engine._journal.create("d1", "Implementar auth JWT")
        engine._journal.set_phase("d1", "dev_working")
        engine._journal.add_decision("d1", "escolha", "JWT sobre sessions")
        engine._lessons.add("bug", "Timeout banco", "Aumentar para 30s")
        engine._daily_notes.add_entry("Migração do banco concluída")

        # Gera prompt
        prompt = engine._build_squad_lead_prompt("d1", "Qual o status?")

        # Verifica que é compacto
        estimated_tokens = ContextBudget.estimate_tokens(prompt)
        assert estimated_tokens < ContextBudget.BUDGET_SQUAD_LEAD * 2, (
            f"Prompt muito grande: ~{estimated_tokens} tokens "
            f"(budget: {ContextBudget.BUDGET_SQUAD_LEAD})"
        )

        # Verifica que contém as seções essenciais
        assert "Squad Lead" in prompt  # AGENTS.md
        assert "user_message" in prompt  # Mensagem do usuário
        assert "Regra de delegacao" in prompt  # Regras
        assert "Qual o status?" in prompt  # Demanda

        # Verifica que NÃO contém seções removidas
        assert "Historico de decisoes (Journal)" not in prompt  # Deduplicado

        # Verifica que contém catálogo on-demand
        assert "query_lessons" in prompt or "Memória disponível" in prompt

    def test_prompt_sem_dados_ainda_compacto(self, tmp_path: Path) -> None:
        """Prompt sem dados (lessons, journal, etc) deve ser mínimo."""
        from ai_squad.adapters.interface import AIAgentAdapter
        from ai_squad.models import AgentStatus
        from ai_squad.orchestrator.context_budget import ContextBudget
        from ai_squad.orchestrator.engine import OrchestrationEngine
        from ai_squad.orchestrator.state import StateManager

        class MockAdapter(AIAgentAdapter):
            async def run(self, prompt: str, context: dict) -> str:  # type: ignore[override]
                return "ok"

            async def ask(self, question: str) -> str:
                return "ok"

            def status(self) -> AgentStatus:
                return AgentStatus.IDLE

            def on_human_needed(self, callback: object) -> None:
                pass

        class MockBus:
            default_chat_id = "123"
            supports_threads = False

            async def send_message(self, *a: object, **kw: object) -> None:
                pass

            async def send_typing(self, *a: object, **kw: object) -> None:
                pass

            async def notify(self, *a: object, **kw: object) -> None:
                pass

            async def ask_user(self, *a: object, **kw: object) -> str:
                return "ok"

            async def send_approval_request(self, *a: object, **kw: object) -> str:
                return "ok"

            async def send_photo(self, *a: object, **kw: object) -> None:
                pass

            def register_personas(self, *a: object) -> None:
                pass

            def mark_agent_active(self, *a: object) -> None:
                pass

            def mark_agent_idle(self, *a: object) -> None:
                pass

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        engine = OrchestrationEngine(
            adapter=MockAdapter(),
            message_bus=MockBus(),  # type: ignore[arg-type]
            state_manager=StateManager(state_dir=str(state_dir)),
            workspace=str(tmp_path),
            agents_dir=str(agents_dir),
            personas={},
        )

        prompt = engine._build_squad_lead_prompt("d1", "Oi")
        estimated_tokens = ContextBudget.estimate_tokens(prompt)

        # Sem dados, deve ser bem compacto (< 2K tokens)
        assert estimated_tokens < 2000, f"Prompt vazio muito grande: ~{estimated_tokens} tokens"


class TestLessonsGetCategories:
    """Testes para LessonsStore.get_categories()."""

    def test_retorna_categorias_unicas(self, tmp_path: Path) -> None:
        store = LessonsStore(state_dir=tmp_path)
        store.add("bug", "Prob 1", "Sol 1")
        store.add("bug", "Prob 2", "Sol 2")
        store.add("processo", "Prob 3", "Sol 3")

        cats = store.get_categories()
        assert "bug" in cats
        assert "processo" in cats
        assert len(cats) == 2

    def test_sem_licoes_retorna_vazio(self, tmp_path: Path) -> None:
        store = LessonsStore(state_dir=tmp_path)
        assert store.get_categories() == []
