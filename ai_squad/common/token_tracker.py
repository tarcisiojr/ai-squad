"""Rastreamento de consumo de tokens por chamada."""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("ai-squad.tokens")


@dataclass
class TokenUsage:
    """Uso de tokens de uma chamada individual."""

    agent_name: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    timestamp: float = field(default_factory=time.time)


class TokenTracker:
    """Acumula uso de tokens por sessão."""

    def __init__(self) -> None:
        self._calls: list[TokenUsage] = []

    def record(
        self,
        agent_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
    ) -> None:
        """Registra uso de tokens de uma chamada."""
        usage = TokenUsage(
            agent_name=agent_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
        )
        self._calls.append(usage)
        logger.info(
            "Tokens: agent=%s model=%s in=%d out=%d duration=%dms",
            agent_name,
            model,
            input_tokens,
            output_tokens,
            duration_ms,
        )

    @property
    def total_input(self) -> int:
        """Total de tokens de entrada."""
        return sum(c.input_tokens for c in self._calls)

    @property
    def total_output(self) -> int:
        """Total de tokens de saída."""
        return sum(c.output_tokens for c in self._calls)

    @property
    def total_tokens(self) -> int:
        """Total de tokens (entrada + saída)."""
        return self.total_input + self.total_output

    @property
    def call_count(self) -> int:
        """Quantidade de chamadas registradas."""
        return len(self._calls)

    def summary(self) -> str:
        """Resumo formatado do consumo de tokens."""
        if not self._calls:
            return "Nenhuma chamada registrada."
        return (
            f"Tokens: {self.total_input:,} in + {self.total_output:,} out "
            f"= {self.total_tokens:,} total "
            f"({self.call_count} chamadas)"
        )
