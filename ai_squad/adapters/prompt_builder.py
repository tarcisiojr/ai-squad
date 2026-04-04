"""Montagem de prompt compartilhada entre adapters de IA."""

from typing import Any


def build_prompt(prompt: str, context: dict[str, Any]) -> str:
    """Monta prompt completo incluindo contexto.

    Extrai campos especiais do context (workspace_context, system_instructions)
    e monta um prompt estruturado com seções.

    Args:
        prompt: Prompt principal do usuário.
        context: Dicionário com contexto adicional. Campos especiais
                 são consumidos (pop) e os demais são listados.

    Returns:
        Prompt completo formatado com seções.
    """
    partes: list[str] = []

    # Contexto do workspace (CLAUDE.md, estrutura, specs)
    product_ctx = context.pop("workspace_context", None)
    if product_ctx:
        partes.append("## Contexto do Projeto")
        partes.append(product_ctx)
        partes.append("")

    # System instructions (AGENTS.md)
    system_instructions = context.pop("system_instructions", None)
    if system_instructions:
        partes.append(system_instructions)
        partes.append("")

    # Filtra chaves internas do contexto
    display_context = {
        k: v
        for k, v in context.items()
        if k not in ("demand_id", "agent_name", "fase", "max_turns")
    }
    if display_context:
        partes.append("## Contexto")
        for chave, valor in display_context.items():
            partes.append(f"- {chave}: {valor}")
        partes.append("")

    partes.append(prompt)

    return "\n".join(partes)
