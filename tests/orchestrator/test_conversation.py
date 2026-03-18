"""Testes para persistência de histórico de conversa."""



from src.orchestrator.conversation import ConversationStore


class TestConversationStore:
    """Testes para ConversationStore."""

    def test_save_e_load_mensagem(self, tmp_path):
        """Verifica salvamento e carregamento de mensagem."""
        store = ConversationStore(str(tmp_path))

        store.save_message("d-001", "agent", "Olá!", "po")
        messages = store.load("d-001")

        assert len(messages) == 1
        assert messages[0]["role"] == "agent"
        assert messages[0]["content"] == "Olá!"
        assert messages[0]["agent_name"] == "po"
        assert "timestamp" in messages[0]

    def test_multiplas_mensagens(self, tmp_path):
        """Verifica que mensagens se acumulam."""
        store = ConversationStore(str(tmp_path))

        store.save_message("d-001", "agent", "Pergunta?", "po")
        store.save_message("d-001", "user", "Resposta!")
        store.save_message("d-001", "agent", "Entendi.", "po")

        messages = store.load("d-001")
        assert len(messages) == 3

    def test_load_inexistente(self, tmp_path):
        """Verifica retorno vazio para demanda inexistente."""
        store = ConversationStore(str(tmp_path))
        messages = store.load("inexistente")
        assert messages == []

    def test_load_json_corrompido(self, tmp_path):
        """Verifica tratamento de JSON corrompido."""
        store = ConversationStore(str(tmp_path))
        demand_dir = tmp_path / "d-bad"
        demand_dir.mkdir()
        (demand_dir / "conversation.json").write_text("não é json")

        messages = store.load("d-bad")
        assert messages == []

    def test_limite_context_messages(self, tmp_path):
        """Verifica limite de mensagens no contexto."""
        store = ConversationStore(str(tmp_path))

        # Salva 25 mensagens
        for i in range(25):
            store.save_message("d-001", "agent", f"Msg {i}", "po")

        context = store.get_context_messages("d-001")

        # Deve ter 20 + 1 resumo = 21
        assert len(context) == 21
        assert context[0]["role"] == "system"
        assert "omitidas" in context[0]["content"]

    def test_format_history_for_prompt(self, tmp_path):
        """Verifica formatação do histórico para prompt."""
        store = ConversationStore(str(tmp_path))

        store.save_message("d-001", "agent", "Como posso ajudar?", "po")
        store.save_message("d-001", "user", "Quero criar um site.")

        history = store.format_history_for_prompt("d-001")

        assert "Histórico da conversa" in history
        assert "po" in history
        assert "Quero criar um site." in history

    def test_format_history_vazio(self, tmp_path):
        """Verifica retorno vazio sem histórico."""
        store = ConversationStore(str(tmp_path))
        history = store.format_history_for_prompt("inexistente")
        assert history == ""

    def test_escrita_atomica(self, tmp_path):
        """Verifica que não existem arquivos .tmp após escrita."""
        store = ConversationStore(str(tmp_path))

        store.save_message("d-001", "agent", "test", "po")

        # Não deve ter arquivos .tmp
        tmp_files = list(tmp_path.rglob("*.tmp"))
        assert len(tmp_files) == 0

    def test_demandas_separadas(self, tmp_path):
        """Verifica isolamento entre demandas."""
        store = ConversationStore(str(tmp_path))

        store.save_message("d-001", "agent", "Msg A", "po")
        store.save_message("d-002", "agent", "Msg B", "dev")

        assert len(store.load("d-001")) == 1
        assert len(store.load("d-002")) == 1
        assert store.load("d-001")[0]["content"] == "Msg A"
        assert store.load("d-002")[0]["content"] == "Msg B"
