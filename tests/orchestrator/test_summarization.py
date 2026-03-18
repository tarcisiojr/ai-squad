"""Testes para sumarização automática de contexto."""

from unittest.mock import AsyncMock

import pytest

from src.orchestrator.conversation import ConversationStore


class TestSummarization:
    """Testes para sumarização automática no ConversationStore."""

    def test_summarize_callback_registrado(self, tmp_path):
        """Verifica registro de callback de sumarização."""
        store = ConversationStore(str(tmp_path))
        callback = AsyncMock(return_value="resumo")
        store.set_summarize_callback(callback)
        assert store._summarize_fn is callback

    @pytest.mark.asyncio
    async def test_sumarizacao_nao_ocorre_abaixo_threshold(self, tmp_path):
        """Verifica que sumarização não ocorre com poucas mensagens."""
        store = ConversationStore(str(tmp_path))
        callback = AsyncMock(return_value="resumo")
        store.set_summarize_callback(callback)

        # Salva 10 mensagens (abaixo do threshold de 20)
        for i in range(10):
            store.save_message("d-001", "agent", f"Msg {i}", "po")

        result = await store.summarize_if_needed("d-001")
        assert result is False
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_sumarizacao_ocorre_acima_threshold(self, tmp_path):
        """Verifica que sumarização ocorre quando ultrapassa threshold."""
        store = ConversationStore(str(tmp_path))
        callback = AsyncMock(return_value="Resumo das mensagens anteriores com decisões e contexto.")
        store.set_summarize_callback(callback)

        # Salva 25 mensagens (acima do threshold de 20)
        for i in range(25):
            store.save_message("d-001", "agent", f"Mensagem número {i}", "po")

        result = await store.summarize_if_needed("d-001")
        assert result is True
        callback.assert_called_once()

        # Verifica que histórico foi reduzido
        messages = store.load("d-001")
        assert len(messages) == store.KEEP_RECENT  # apenas as recentes

        # Verifica que resumo foi salvo
        summary = store.load_summary("d-001")
        assert "Resumo das mensagens" in summary

    @pytest.mark.asyncio
    async def test_sumarizacao_sem_callback(self, tmp_path):
        """Verifica que sem callback, sumarização não ocorre."""
        store = ConversationStore(str(tmp_path))

        for i in range(25):
            store.save_message("d-001", "agent", f"Msg {i}", "po")

        result = await store.summarize_if_needed("d-001")
        assert result is False

    @pytest.mark.asyncio
    async def test_sumarizacao_acumula_resumos(self, tmp_path):
        """Verifica que resumos são acumulados entre sumarizações."""
        store = ConversationStore(str(tmp_path))
        call_count = 0

        async def mock_summarize(text):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "Primeiro resumo"
            return "Resumo acumulado com primeiro e segundo"

        store.set_summarize_callback(mock_summarize)

        # Primeira rodada: 25 mensagens
        for i in range(25):
            store.save_message("d-001", "agent", f"Lote 1 msg {i}", "po")

        await store.summarize_if_needed("d-001")
        assert store.load_summary("d-001") == "Primeiro resumo"

        # Segunda rodada: mais 25 mensagens
        for i in range(25):
            store.save_message("d-001", "agent", f"Lote 2 msg {i}", "po")

        await store.summarize_if_needed("d-001")
        assert "acumulado" in store.load_summary("d-001")

    @pytest.mark.asyncio
    async def test_sumarizacao_falha_nao_perde_dados(self, tmp_path):
        """Verifica que falha na sumarização não perde mensagens."""
        store = ConversationStore(str(tmp_path))
        callback = AsyncMock(side_effect=RuntimeError("Erro LLM"))
        store.set_summarize_callback(callback)

        for i in range(25):
            store.save_message("d-001", "agent", f"Msg {i}", "po")

        result = await store.summarize_if_needed("d-001")
        assert result is False

        # Mensagens devem estar intactas
        messages = store.load("d-001")
        assert len(messages) == 25

    @pytest.mark.asyncio
    async def test_sumarizacao_resumo_muito_curto_ignorado(self, tmp_path):
        """Verifica que resumo muito curto é ignorado."""
        store = ConversationStore(str(tmp_path))
        callback = AsyncMock(return_value="ok")
        store.set_summarize_callback(callback)

        for i in range(25):
            store.save_message("d-001", "agent", f"Msg {i}", "po")

        result = await store.summarize_if_needed("d-001")
        assert result is False  # resumo curto demais

    def test_get_context_messages_com_summary(self, tmp_path):
        """Verifica que context messages inclui resumo quando disponível."""
        store = ConversationStore(str(tmp_path))

        # Salva resumo manualmente
        store._save_summary("d-001", "Resumo das conversas anteriores")

        # Salva algumas mensagens
        for i in range(5):
            store.save_message("d-001", "agent", f"Msg {i}", "po")

        context = store.get_context_messages("d-001")

        # Primeira mensagem deve ser o resumo
        assert context[0]["role"] == "system"
        assert "Resumo das conversas anteriores" in context[0]["content"]
        assert len(context) == 6  # 1 resumo + 5 mensagens

    def test_format_history_com_summary(self, tmp_path):
        """Verifica formatação do histórico com resumo."""
        store = ConversationStore(str(tmp_path))

        store._save_summary("d-001", "Resumo: decisões importantes foram tomadas")
        store.save_message("d-001", "user", "Nova mensagem")

        history = store.format_history_for_prompt("d-001")

        assert "Resumo" in history
        assert "Nova mensagem" in history

    def test_message_count(self, tmp_path):
        """Verifica contagem de mensagens."""
        store = ConversationStore(str(tmp_path))

        assert store.message_count("d-001") == 0

        store.save_message("d-001", "user", "msg 1")
        store.save_message("d-001", "agent", "msg 2")

        assert store.message_count("d-001") == 2

    def test_fsync_na_escrita(self, tmp_path):
        """Verifica que escrita atômica usa fsync (não gera .tmp residuais)."""
        store = ConversationStore(str(tmp_path))
        store.save_message("d-001", "agent", "teste", "po")

        # Nenhum .tmp residual
        tmp_files = list(tmp_path.rglob("*.tmp"))
        assert len(tmp_files) == 0

    def test_load_summary_inexistente(self, tmp_path):
        """Verifica retorno vazio para resumo inexistente."""
        store = ConversationStore(str(tmp_path))
        assert store.load_summary("inexistente") == ""
