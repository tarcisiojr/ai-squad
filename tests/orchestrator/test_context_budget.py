"""Testes unitários para ContextBudget — distribuição de tokens por tiers."""

import pytest

from ai_squad.orchestrator.context_budget import (
    ContextBudget,
    shrink_conversation,
    shrink_lessons,
    shrink_workspace,
)


class TestEstimateTokens:
    """Testes para estimativa de tokens."""

    def test_texto_vazio(self) -> None:
        assert ContextBudget.estimate_tokens("") == 0

    def test_texto_curto(self) -> None:
        # 30 chars → ~10 tokens
        result = ContextBudget.estimate_tokens("a" * 30)
        assert result == 10

    def test_texto_portugues(self) -> None:
        texto = "Este é um texto em português para testar a estimativa."
        tokens = ContextBudget.estimate_tokens(texto)
        assert tokens > 0
        assert tokens == len(texto) // 3


class TestTierDistribution:
    """Testes para distribuição de tokens por tiers."""

    def test_budget_suficiente_inclui_todos_tiers(self) -> None:
        """Quando budget é suficiente, todos os tiers são incluídos."""
        budget = ContextBudget(total_budget=10000)
        budget.add(1, "instructions", "instrucoes do agente")
        budget.add(2, "conversation", "historico de conversa")
        budget.add(3, "daily_notes", "notas do dia")

        result = budget.build()
        assert "instrucoes do agente" in result
        assert "historico de conversa" in result
        assert "notas do dia" in result

    def test_tier3_descartado_quando_sem_budget(self) -> None:
        """Tier 3 é descartado quando não há budget restante."""
        budget = ContextBudget(total_budget=30)
        budget.add(1, "critical", "a" * 60)  # ~20 tokens
        budget.add(2, "relevant", "b" * 30)  # ~10 tokens
        budget.add(3, "optional", "c" * 30)  # ~10 tokens, não cabe

        result = budget.build()
        assert "a" * 60 in result  # Tier 1 sempre
        assert "b" * 30 in result  # Tier 2 cabe
        assert "c" * 30 not in result  # Tier 3 descartado

    def test_tier1_nunca_truncado(self) -> None:
        """Tier 1 nunca é truncado, mesmo se excede budget."""
        budget = ContextBudget(total_budget=5)
        budget.add(1, "critical", "texto critico muito importante")

        result = budget.build()
        assert "texto critico muito importante" in result

    def test_tier2_encolhe_via_shrink_fn(self) -> None:
        """Tier 2 usa shrink_fn quando não cabe no budget."""
        def fake_shrink(content: str, max_tokens: int) -> str:
            return "resumo"

        budget = ContextBudget(total_budget=20)
        budget.add(1, "critical", "abc")  # ~1 token
        budget.add(2, "big", "x" * 300, shrink_fn=fake_shrink)  # ~100 tokens, não cabe

        result = budget.build()
        assert "abc" in result
        assert "resumo" in result

    def test_secao_vazia_ignorada(self) -> None:
        """Seções vazias não são adicionadas."""
        budget = ContextBudget(total_budget=1000)
        budget.add(1, "empty", "")
        budget.add(1, "spaces", "   ")
        budget.add(1, "real", "conteudo real")

        result = budget.build()
        assert "conteudo real" in result
        assert result.strip() == "conteudo real"

    def test_tier_invalido_levanta_erro(self) -> None:
        """Tier fora do range 1-3 levanta ValueError."""
        budget = ContextBudget(total_budget=1000)
        with pytest.raises(ValueError):
            budget.add(4, "invalid", "conteudo")


class TestUsageReport:
    """Testes para relatório de uso."""

    def test_report_basico(self) -> None:
        budget = ContextBudget(total_budget=5000)
        budget.add(1, "instructions", "abc")
        budget.add(2, "conversation", "def ghi")
        budget.add(3, "notes", "jkl")

        report = budget.usage_report()
        assert report["total_budget"] == 5000
        assert "t1_instructions" in report
        assert "t2_conversation" in report
        assert "t3_notes" in report
        assert report["tier_1_total"] > 0
        assert report["total_used"] > 0
        assert report["remaining"] > 0


class TestBudgetPorPapel:
    """Testes para budgets padrão por papel."""

    def test_budget_squad_lead(self) -> None:
        assert ContextBudget.BUDGET_SQUAD_LEAD == 8000

    def test_budget_agent_task(self) -> None:
        assert ContextBudget.BUDGET_AGENT_TASK == 4000

    def test_budget_agent_review(self) -> None:
        assert ContextBudget.BUDGET_AGENT_REVIEW == 6000


class TestShrinkLessons:
    """Testes para shrink_fn de lições."""

    def test_reduz_itens(self) -> None:
        content = (
            "## Licoes aprendidas\n"
            "- item 1\n"
            "- item 2\n"
            "- item 3\n"
            "- item 4\n"
            "- item 5\n"
            "- item 6\n"
            "- item 7\n"
            "- item 8\n"
            "- item 9\n"
            "- item 10"
        )
        result = shrink_lessons(content, 50)
        # Deve ter reduzido o número de itens
        assert result.count("- item") < 10

    def test_retorna_vazio_se_budget_zero(self) -> None:
        assert shrink_lessons("- item 1\n- item 2", 0) == ""


class TestShrinkConversation:
    """Testes para shrink_fn de conversa."""

    def test_mantem_mensagens_recentes(self) -> None:
        content = (
            "## Historico\n"
            "msg antiga 1\n"
            "msg antiga 2\n"
            "msg recente 1\n"
            "msg recente 2"
        )
        result = shrink_conversation(content, 20)
        # Deve manter pelo menos a mensagem mais recente
        assert "msg recente 2" in result

    def test_retorna_vazio_se_sem_conteudo(self) -> None:
        assert shrink_conversation("", 100) == ""


class TestShrinkWorkspace:
    """Testes para shrink_fn de workspace."""

    def test_mantem_headers(self) -> None:
        content = (
            "## Arquitetura\n"
            "Texto detalhado sobre arquitetura que é muito longo.\n"
            "## Padrões\n"
            "- Padrão 1\n"
            "- Padrão 2\n"
            "Mais texto irrelevante."
        )
        result = shrink_workspace(content, 30)
        assert "## Arquitetura" in result
        assert "## Padrões" in result

    def test_retorna_vazio_se_sem_conteudo(self) -> None:
        assert shrink_workspace("", 100) == ""
