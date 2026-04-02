"""Testes para MessageContext."""

from ai_squad.messaging.context import MessageContext


class TestMessageContext:
    """Testes unitários para MessageContext."""

    def test_criacao_completa(self):
        """Cria MessageContext com todos os campos."""
        ctx = MessageContext(
            chat_id="grupo-999",
            user_id="111",
            thread_id=123,
            demand_id="login-a1b2",
        )
        assert ctx.chat_id == "grupo-999"
        assert ctx.user_id == "111"
        assert ctx.thread_id == 123
        assert ctx.demand_id == "login-a1b2"

    def test_valores_default(self):
        """Thread_id e demand_id são None por padrão."""
        ctx = MessageContext(chat_id="12345", user_id="12345")
        assert ctx.thread_id is None
        assert ctx.demand_id is None

    def test_dm_chat_e_user_iguais(self):
        """Em DM, chat_id e user_id são iguais."""
        ctx = MessageContext(chat_id="12345", user_id="12345")
        assert ctx.chat_id == ctx.user_id

    def test_grupo_chat_e_user_diferentes(self):
        """Em grupo, chat_id e user_id são diferentes."""
        ctx = MessageContext(chat_id="grupo-999", user_id="111")
        assert ctx.chat_id != ctx.user_id
