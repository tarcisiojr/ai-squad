"""Gerenciamento de orçamento de tokens para montagem de prompts.

Distribui tokens por prioridade (tiers) com shrink progressivo,
garantindo que o prompt final respeita um budget total.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger("ai-squad.context-budget")


@dataclass
class Section:
    """Seção de contexto com metadata para o budget."""

    name: str
    content: str
    shrink_fn: Callable[[str, int], str] | None = None
    tokens: int = 0


class ContextBudget:
    """Gerencia orçamento de tokens do prompt.

    Distribui tokens em 3 tiers com prioridades distintas:
    - Tier 1 (crítico): sempre presente, nunca truncado
    - Tier 2 (relevante): encolhível via shrink_fn por prioridade inversa
    - Tier 3 (complementar): incluído apenas se sobrar budget
    """

    # Budgets padrão por papel
    BUDGET_SQUAD_LEAD = 8000
    BUDGET_AGENT_TASK = 4000
    BUDGET_AGENT_REVIEW = 6000

    def __init__(self, total_budget: int = 8000) -> None:
        self._budget = total_budget
        self._tiers: dict[int, list[Section]] = {1: [], 2: [], 3: []}
        self._built = False

    @property
    def total_budget(self) -> int:
        """Budget total configurado."""
        return self._budget

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estima contagem de tokens por divisão de caracteres.

        Precisão ~85% para português/código misto (~3.3 chars/token).
        """
        if not text:
            return 0
        return len(text) // 3

    def add(
        self,
        tier: int,
        name: str,
        content: str,
        shrink_fn: Callable[[str, int], str] | None = None,
    ) -> None:
        """Adiciona seção ao tier especificado.

        Args:
            tier: Prioridade (1=crítico, 2=relevante, 3=complementar).
            name: Identificador da seção (para relatório).
            content: Texto da seção.
            shrink_fn: Função que reduz conteúdo para caber em N tokens.
                       Assinatura: (content, max_tokens) -> compressed_content.
        """
        if not content or not content.strip():
            return
        if tier not in (1, 2, 3):
            raise ValueError(f"Tier deve ser 1, 2 ou 3 (recebido: {tier})")

        tokens = self.estimate_tokens(content)
        section = Section(name=name, content=content, shrink_fn=shrink_fn, tokens=tokens)
        self._tiers[tier].append(section)

    def build(self) -> str:
        """Monta prompt final respeitando budget por prioridade.

        Retorna texto concatenado das seções que cabem no budget.
        """
        parts: list[str] = []
        used = 0

        # Tier 1: sempre entra (nunca trunca)
        for section in self._tiers[1]:
            parts.append(section.content)
            used += section.tokens

        if used > self._budget:
            logger.warning(
                "Tier 1 excede budget total (%d > %d). Incluindo mesmo assim.",
                used,
                self._budget,
            )

        remaining = max(0, self._budget - used)

        # Tier 2: encolhe por prioridade inversa se necessário
        tier2 = list(self._tiers[2])
        tier2_total = sum(s.tokens for s in tier2)

        if tier2_total <= remaining:
            # Cabe tudo
            for section in tier2:
                parts.append(section.content)
                remaining -= section.tokens
        else:
            # Precisa encolher — prioridade inversa (último adicionado encolhe primeiro)
            for section in reversed(tier2):
                if section.tokens <= remaining:
                    parts.append(section.content)
                    remaining -= section.tokens
                elif section.shrink_fn and remaining > 0:
                    shrunk = section.shrink_fn(section.content, remaining)
                    shrunk_tokens = self.estimate_tokens(shrunk)
                    if shrunk and shrunk_tokens <= remaining:
                        parts.append(shrunk)
                        remaining -= shrunk_tokens
                        logger.info(
                            "Seção '%s' encolhida: %d → %d tokens",
                            section.name,
                            section.tokens,
                            shrunk_tokens,
                        )
                    else:
                        logger.info("Seção '%s' descartada (shrink insuficiente)", section.name)
                else:
                    logger.info(
                        "Seção '%s' descartada (sem budget: %d tokens, restam %d)",
                        section.name,
                        section.tokens,
                        remaining,
                    )

        # Tier 3: só se sobrou budget
        for section in self._tiers[3]:
            if section.tokens <= remaining:
                parts.append(section.content)
                remaining -= section.tokens
            else:
                logger.debug("Tier 3 '%s' descartado (sem budget restante)", section.name)

        self._built = True
        return "\n\n".join(parts)

    def usage_report(self) -> dict[str, int]:
        """Retorna consumo de tokens por tier e por componente."""
        report: dict[str, int] = {"total_budget": self._budget}
        total_used = 0

        for tier_num, sections in self._tiers.items():
            tier_total = 0
            for section in sections:
                report[f"t{tier_num}_{section.name}"] = section.tokens
                tier_total += section.tokens
            report[f"tier_{tier_num}_total"] = tier_total
            total_used += tier_total

        report["total_used"] = total_used
        report["remaining"] = max(0, self._budget - total_used)
        return report


# --- Shrink functions pré-definidas ---


def shrink_lessons(content: str, max_tokens: int) -> str:
    """Reduz lessons mantendo apenas as mais relevantes.

    Estratégia: reduz de 10 para 5, depois 3 itens.
    """
    lines = content.strip().split("\n")
    if not lines:
        return ""

    # Preserva header
    header = lines[0] if lines[0].startswith("#") else ""
    items = [line for line in lines if line.startswith("- ")]

    for limit in (5, 3, 1):
        if len(items) > limit:
            items = items[:limit]
        candidate = header + "\n" + "\n".join(items) if header else "\n".join(items)
        if ContextBudget.estimate_tokens(candidate) <= max_tokens:
            return candidate

    return ""


def shrink_conversation(content: str, max_tokens: int) -> str:
    """Reduz conversa mantendo mensagens mais recentes.

    Estratégia: mantém as últimas N mensagens que cabem no budget.
    """
    lines = content.strip().split("\n")
    if not lines:
        return ""

    # Preserva header se existir
    header = ""
    if lines and lines[0].startswith("#"):
        header = lines[0]
        lines = lines[1:]

    # Tenta incluir de trás pra frente
    result: list[str] = []
    used = ContextBudget.estimate_tokens(header) if header else 0

    for line in reversed(lines):
        line_tokens = ContextBudget.estimate_tokens(line)
        if used + line_tokens <= max_tokens:
            result.insert(0, line)
            used += line_tokens
        else:
            break

    if not result:
        return ""

    if header:
        return header + "\n" + "\n".join(result)
    return "\n".join(result)


def shrink_workspace(content: str, max_tokens: int) -> str:
    """Reduz workspace context extraindo apenas headers e seções-chave.

    Estratégia: mantém apenas linhas de header (##, ###) e primeiras linhas.
    """
    lines = content.strip().split("\n")
    if not lines:
        return ""

    # Extrai headers e primeiras linhas de cada seção
    result: list[str] = []
    used = 0

    for line in lines:
        is_header = line.startswith("#")
        is_important = line.startswith("- ") or line.startswith("```")

        if is_header or is_important:
            line_tokens = ContextBudget.estimate_tokens(line)
            if used + line_tokens <= max_tokens:
                result.append(line)
                used += line_tokens

    return "\n".join(result) if result else ""
