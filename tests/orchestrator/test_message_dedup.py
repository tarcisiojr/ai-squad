"""Testes para deduplicação de mensagens — canal interno vs externo.

Valida que report_progress armazena no progress_log,
on_agent_done não envia direto ao usuário, e o histórico
marca mensagens internas corretamente.
"""

from src.orchestrator.conversation import ConversationStore
from src.orchestrator.tools import RunningAgent


class TestRunningAgentProgressLog:
    """Testes para o campo progress_log do RunningAgent."""

    def test_progress_log_inicializa_vazio(self):
        """Verifica que progress_log começa vazio."""
        agent = RunningAgent(agent_name="dev", demand_id="d-001")
        assert agent.progress_log == []
        assert agent.status_sent is False

    def test_progress_log_acumula_mensagens(self):
        """Verifica que progress_log acumula mensagens."""
        agent = RunningAgent(agent_name="dev", demand_id="d-001")
        agent.progress_log.append("Analisando código...")
        agent.progress_log.append("Encontrei 3 issues")
        assert len(agent.progress_log) == 2

    def test_status_sent_flag(self):
        """Verifica controle de status leve enviado."""
        agent = RunningAgent(agent_name="dev", demand_id="d-001")
        assert agent.status_sent is False
        agent.status_sent = True
        assert agent.status_sent is True

    def test_progress_log_isolado_entre_agentes(self):
        """Verifica que cada agente tem seu próprio progress_log."""
        agent1 = RunningAgent(agent_name="dev", demand_id="d-001")
        agent2 = RunningAgent(agent_name="qa", demand_id="d-001")
        agent1.progress_log.append("msg dev")
        assert len(agent2.progress_log) == 0


class TestConversationInternalMessages:
    """Testes para mensagens internas no histórico de conversa."""

    def test_mensagem_interna_salva_com_role_internal(self, tmp_path):
        """Verifica que mensagens internas são salvas corretamente."""
        store = ConversationStore(str(tmp_path))
        store.save_message("d-001", "internal", "dev concluiu: resultado", agent_name="dev")

        messages = store.load("d-001")
        assert len(messages) == 1
        assert messages[0]["role"] == "internal"

    def test_format_history_marca_mensagem_interna(self, tmp_path):
        """Verifica que mensagens internas são marcadas no prompt."""
        store = ConversationStore(str(tmp_path))
        store.save_message("d-001", "user", "Criar feature X")
        store.save_message("d-001", "internal", "dev concluiu: análise ok", agent_name="dev")
        store.save_message("d-001", "assistant", "Dev analisou. Próximo: QA.", agent_name="squad-lead")

        history = store.format_history_for_prompt("d-001")

        # Mensagem interna deve estar marcada
        assert "interno, usuario nao viu" in history
        # Mensagem do usuário e do squad lead não devem ter marcação
        assert history.count("interno, usuario nao viu") == 1

    def test_format_history_mensagem_normal_sem_marcacao(self, tmp_path):
        """Verifica que mensagens normais não ganham marcação interna."""
        store = ConversationStore(str(tmp_path))
        store.save_message("d-001", "assistant", "Tudo certo!", agent_name="squad-lead")

        history = store.format_history_for_prompt("d-001")
        assert "interno" not in history

    def test_mensagens_mistas_no_historico(self, tmp_path):
        """Verifica formatação com mensagens normais e internas misturadas."""
        store = ConversationStore(str(tmp_path))
        store.save_message("d-001", "user", "Implementar login")
        store.save_message("d-001", "assistant", "Vou delegar ao Dev.", agent_name="squad-lead")
        store.save_message("d-001", "internal", "dev concluiu: login implementado", agent_name="dev")
        store.save_message("d-001", "assistant", "Dev implementou o login.", agent_name="squad-lead")

        history = store.format_history_for_prompt("d-001")
        lines = history.strip().split("\n")

        # Deve ter header + 4 mensagens (com linhas em branco entre elas)
        content_lines = [l for l in lines if l.strip() and "Histórico" not in l]
        assert len(content_lines) == 4
        # Apenas 1 deve ser interna
        internal_lines = [l for l in content_lines if "interno" in l]
        assert len(internal_lines) == 1
