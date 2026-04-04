"""Testes para o rastreamento de tokens."""

from ai_squad.common.token_tracker import TokenTracker, TokenUsage


class TestTokenUsage:
    """Testes para o dataclass TokenUsage."""

    def test_cria_usage_com_campos_corretos(self) -> None:
        usage = TokenUsage(
            agent_name="dev",
            model="claude-sonnet",
            input_tokens=100,
            output_tokens=50,
            duration_ms=1200,
        )
        assert usage.agent_name == "dev"
        assert usage.model == "claude-sonnet"
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.duration_ms == 1200
        assert usage.timestamp > 0


class TestTokenTracker:
    """Testes para o acumulador de tokens."""

    def test_tracker_vazio_retorna_zeros(self) -> None:
        tracker = TokenTracker()
        assert tracker.total_input == 0
        assert tracker.total_output == 0
        assert tracker.total_tokens == 0
        assert tracker.call_count == 0

    def test_record_armazena_uso_corretamente(self) -> None:
        tracker = TokenTracker()
        tracker.record(
            agent_name="squad-lead",
            model="claude-sonnet",
            input_tokens=500,
            output_tokens=200,
            duration_ms=3000,
        )
        assert tracker.call_count == 1
        assert tracker.total_input == 500
        assert tracker.total_output == 200
        assert tracker.total_tokens == 700

    def test_totais_acumulam_multiplas_chamadas(self) -> None:
        tracker = TokenTracker()
        tracker.record("agent-a", "model-1", 100, 50, 1000)
        tracker.record("agent-b", "model-2", 200, 100, 2000)
        tracker.record("agent-a", "model-1", 300, 150, 1500)

        assert tracker.total_input == 600
        assert tracker.total_output == 300
        assert tracker.total_tokens == 900
        assert tracker.call_count == 3

    def test_summary_tracker_vazio(self) -> None:
        tracker = TokenTracker()
        assert tracker.summary() == "Nenhuma chamada registrada."

    def test_summary_formata_corretamente(self) -> None:
        tracker = TokenTracker()
        tracker.record("squad-lead", "claude-sonnet", 1000, 500, 2000)
        tracker.record("dev", "claude-haiku", 2000, 800, 1500)

        summary = tracker.summary()
        assert "3,000 in" in summary
        assert "1,300 out" in summary
        assert "4,300 total" in summary
        assert "2 chamadas" in summary

    def test_summary_com_uma_chamada(self) -> None:
        tracker = TokenTracker()
        tracker.record("dev", "model-x", 42, 18, 500)

        summary = tracker.summary()
        assert "42 in" in summary
        assert "18 out" in summary
        assert "60 total" in summary
        assert "1 chamadas" in summary
