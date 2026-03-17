"""Testes para fallback chain com retry inteligente."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter


class TestRetryLogic:
    """Testes para lógica de retry no adapter."""

    @pytest.fixture
    def adapter(self):
        """Cria instância do adapter para testes."""
        return ClaudeAgentSDKAdapter(timeout=30)

    @pytest.mark.asyncio
    async def test_retry_em_erro_generico(self, adapter):
        """Verifica retry com backoff em erro genérico."""
        call_count = 0

        mock_text_block = MagicMock()
        mock_text_block.text = "Sucesso"
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        async def mock_query(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Erro temporário")
            yield mock_message

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query
        ), patch(
            "src.adapters.claude_agent_sdk.AssistantMessage",
            type(mock_message),
        ), patch(
            "src.adapters.claude_agent_sdk.TextBlock",
            type(mock_text_block),
        ), patch("asyncio.sleep", new_callable=AsyncMock):
            resultado = await adapter._execute_sdk(
                "teste", agent_name="test-agent",
            )

        assert resultado == "Sucesso"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_esgota_retries(self, adapter):
        """Verifica que esgota todas as tentativas e propaga erro."""
        async def mock_query(**kwargs):
            raise RuntimeError("Erro persistente")
            yield  # pragma: no cover

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query
        ), patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="Erro persistente"):
                await adapter._execute_sdk(
                    "teste", agent_name="test-agent",
                )

    @pytest.mark.asyncio
    async def test_timeout_nao_faz_retry(self, adapter):
        """Verifica que timeout propaga imediatamente sem retry."""
        call_count = 0

        async def mock_query(**kwargs):
            nonlocal call_count
            call_count += 1
            raise asyncio.TimeoutError()
            yield  # pragma: no cover

        adapter._timeout = 1

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query
        ):
            with pytest.raises(asyncio.TimeoutError):
                await adapter._execute_sdk(
                    "teste", agent_name="test-agent", timeout=1,
                )

        assert call_count == 1  # sem retry

    @pytest.mark.asyncio
    async def test_context_length_exceeded_comprime_e_retenta(self, adapter):
        """Verifica compressão de prompt em context_length_exceeded."""
        call_count = 0

        mock_text_block = MagicMock()
        mock_text_block.text = "Sucesso após compressão"
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        async def mock_query(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("context_length_exceeded: prompt is too long")
            yield mock_message

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query
        ), patch(
            "src.adapters.claude_agent_sdk.AssistantMessage",
            type(mock_message),
        ), patch(
            "src.adapters.claude_agent_sdk.TextBlock",
            type(mock_text_block),
        ):
            resultado = await adapter._execute_sdk(
                "prompt longo " * 100, agent_name="test-agent",
            )

        assert resultado == "Sucesso após compressão"
        assert call_count == 2


class TestCompressPrompt:
    """Testes para compressão de prompt."""

    def test_prompt_curto(self):
        """Prompt curto é cortado pela metade."""
        prompt = "\n".join(f"Linha {i}" for i in range(40))
        compressed = ClaudeAgentSDKAdapter._compress_prompt(prompt)

        assert "contexto comprimido" in compressed
        # Verifica que linhas intermediárias foram removidas
        assert compressed.count("\n") < prompt.count("\n")

    def test_prompt_longo(self):
        """Prompt longo remove linhas intermediárias."""
        prompt = "\n".join(f"Linha {i}" for i in range(200))
        compressed = ClaudeAgentSDKAdapter._compress_prompt(prompt)

        assert "linhas de contexto removidas" in compressed
        assert len(compressed.split("\n")) < 200

    def test_prompt_muito_curto_nao_quebra(self):
        """Prompt com poucas linhas não quebra."""
        prompt = "Linha 1\nLinha 2\nLinha 3"
        compressed = ClaudeAgentSDKAdapter._compress_prompt(prompt)

        assert "contexto comprimido" in compressed


class TestModelOverride:
    """Testes para model override no run."""

    @pytest.fixture
    def adapter(self):
        return ClaudeAgentSDKAdapter(
            timeout=30, model="claude-sonnet-4-20250514",
        )

    @pytest.mark.asyncio
    async def test_model_override_temporario(self, adapter):
        """Verifica que model_override é temporário e restaurado."""
        mock_text_block = MagicMock()
        mock_text_block.text = "ok"
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        async def mock_query(**kwargs):
            yield mock_message

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query
        ), patch(
            "src.adapters.claude_agent_sdk.AssistantMessage",
            type(mock_message),
        ), patch(
            "src.adapters.claude_agent_sdk.TextBlock",
            type(mock_text_block),
        ):
            await adapter.run(
                "teste",
                {"model_override": "claude-haiku-4-5-20251001"},
            )

        # Modelo deve ter sido restaurado
        assert adapter._model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_model_override_restaurado_apos_erro(self, adapter):
        """Verifica restauração do modelo mesmo após erro."""
        async def mock_query_erro(**kwargs):
            raise RuntimeError("Erro")
            yield  # pragma: no cover

        with patch(
            "src.adapters.claude_agent_sdk.query", side_effect=mock_query_erro
        ), patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await adapter.run(
                    "teste",
                    {"model_override": "claude-haiku-4-5-20251001"},
                )

        assert adapter._model == "claude-sonnet-4-20250514"
