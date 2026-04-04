"""Retry com backoff exponencial — utility compartilhado."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger("ai-squad.retry")

T = TypeVar("T")

# Padrões de erros transientes (HTTP, SDK, rede)
TRANSIENT_PATTERNS: tuple[str, ...] = (
    "overloaded",
    "rate_limit",
    "rate limit",
    "429",
    "502",
    "503",
    "529",
    "connection",
    "timeout",
    "temporary",
    "unavailable",
)


def is_transient_error(error: Exception) -> bool:
    """Verifica se o erro é transiente e pode ser retentado."""
    msg = str(error).lower()
    return any(p in msg for p in TRANSIENT_PATTERNS)


async def retry_with_backoff(
    fn: Callable[..., Awaitable[T]],
    *,
    max_retries: int = 2,
    base_delay: float = 2.0,
    is_transient: Callable[[Exception], bool] = is_transient_error,
    time_budget: float | None = None,
    min_budget_for_retry: float = 30.0,
) -> T:
    """Executa fn com retry e backoff exponencial.

    Args:
        fn: Função async a executar.
        max_retries: Número máximo de retries (total = max_retries + 1).
        base_delay: Delay base em segundos (dobra a cada retry).
        is_transient: Função que verifica se o erro é retentável.
        time_budget: Tempo total disponível (None = sem limite).
        min_budget_for_retry: Tempo mínimo restante para permitir retry.
    """
    start = time.monotonic()
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            is_last = attempt == max_retries
            if is_last or not is_transient(e):
                raise

            # Verifica budget de tempo restante
            if time_budget is not None:
                elapsed = time.monotonic() - start
                remaining = time_budget - elapsed
                if remaining < min_budget_for_retry:
                    logger.warning(
                        "Budget esgotado (%.1fs restantes), sem retry: %s",
                        remaining,
                        e,
                    )
                    raise

            delay = base_delay * (2**attempt)
            logger.info(
                "Retry %d/%d em %.1fs: %s",
                attempt + 1,
                max_retries,
                delay,
                e,
            )
            await asyncio.sleep(delay)

    # Inalcançável, mas satisfaz o type checker
    assert last_error is not None  # noqa: S101
    raise last_error
