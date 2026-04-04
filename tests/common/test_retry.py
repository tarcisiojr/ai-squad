"""Testes para ai_squad.common.retry."""

import asyncio

import pytest

from ai_squad.common.retry import is_transient_error, retry_with_backoff


# --- is_transient_error ---


class TestIsTransientError:
    def test_erro_transiente_por_padrao(self) -> None:
        assert is_transient_error(Exception("rate_limit exceeded"))

    def test_erro_429(self) -> None:
        assert is_transient_error(Exception("HTTP 429 Too Many Requests"))

    def test_erro_502(self) -> None:
        assert is_transient_error(Exception("502 Bad Gateway"))

    def test_erro_conexao(self) -> None:
        assert is_transient_error(Exception("connection refused"))

    def test_erro_nao_transiente(self) -> None:
        assert not is_transient_error(Exception("invalid api key"))

    def test_erro_overloaded(self) -> None:
        assert is_transient_error(Exception("server overloaded"))


# --- retry_with_backoff ---


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_sucesso_na_primeira_tentativa(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        resultado = await retry_with_backoff(fn, base_delay=0.01)
        assert resultado == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_apos_erro_transiente(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("rate_limit exceeded")
            return "ok"

        resultado = await retry_with_backoff(fn, base_delay=0.01)
        assert resultado == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_erro_nao_transiente_propaga_imediatamente(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            raise Exception("invalid api key")

        with pytest.raises(Exception, match="invalid api key"):
            await retry_with_backoff(fn, base_delay=0.01)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_excedido(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            raise Exception("rate_limit exceeded")

        with pytest.raises(Exception, match="rate_limit"):
            await retry_with_backoff(fn, max_retries=2, base_delay=0.01)
        assert call_count == 3  # 1 original + 2 retries

    @pytest.mark.asyncio
    async def test_budget_de_tempo_impede_retry(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            raise Exception("timeout error")

        with pytest.raises(Exception, match="timeout"):
            await retry_with_backoff(
                fn,
                max_retries=3,
                base_delay=0.01,
                time_budget=0.1,
                min_budget_for_retry=0.08,
            )
        # Deve parar antes do max_retries por budget esgotado
        assert call_count <= 2

    @pytest.mark.asyncio
    async def test_is_transient_customizado(self) -> None:
        call_count = 0

        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            raise Exception("custom error")

        # Erro customizado tratado como transiente
        with pytest.raises(Exception, match="custom"):
            await retry_with_backoff(
                fn,
                max_retries=1,
                base_delay=0.01,
                is_transient=lambda _: True,
            )
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_backoff_exponencial(self) -> None:
        """Verifica que delays crescem exponencialmente."""
        import time

        timestamps: list[float] = []

        async def fn() -> str:
            timestamps.append(time.monotonic())
            if len(timestamps) < 3:
                raise Exception("rate_limit")
            return "ok"

        await retry_with_backoff(fn, max_retries=2, base_delay=0.05)

        # Segundo delay (~0.1s) deve ser maior que primeiro (~0.05s)
        delay1 = timestamps[1] - timestamps[0]
        delay2 = timestamps[2] - timestamps[1]
        assert delay2 > delay1
