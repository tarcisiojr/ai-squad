"""Roteamento de modelo por complexidade da mensagem.

Classifica mensagens do usuário para decidir se devem ser processadas
por um modelo leve (rápido/barato) ou pesado (capaz/caro).
Inspirado no RuleClassifier do PicoClaw.
"""

import logging
import re

logger = logging.getLogger("ai-squad.model-router")

# Palavras-chave que indicam necessidade de modelo pesado
_HEAVY_KEYWORDS = {
    # Delegação e coordenação
    "implementar",
    "implementa",
    "criar",
    "crie",
    "desenvolver",
    "desenvolva",
    "refatorar",
    "refatora",
    "migrar",
    "migra",
    "deploy",
    "deploye",
    # Especificação
    "especificar",
    "especifique",
    "demandar",
    "demanda",
    "planejar",
    "spec",
    "openspec",
    "proposal",
    "design",
    # Código e técnico
    "bug",
    "erro",
    "fix",
    "corrigir",
    "debug",
    "teste",
    "test",
    "commit",
    "pull",
    "merge",
    "branch",
    # Agentes
    "delegar",
    "delegue",
    "start_agent",
    "agente",
    # Análise complexa
    "analisar",
    "analise",
    "revisar",
    "review",
    "arquitetura",
}

# Padrões que indicam código
_CODE_PATTERNS = [
    re.compile(r"```"),  # code blocks
    re.compile(r"def\s+\w+"),  # python function
    re.compile(r"class\s+\w+"),  # class definition
    re.compile(r"import\s+\w+"),  # imports
    re.compile(r"\w+\.\w+\("),  # method calls
    re.compile(r"->|=>"),  # arrows
]


def classify_complexity(message: str) -> str:
    """Classifica complexidade da mensagem.

    Retorna 'heavy' para mensagens que precisam de modelo capaz,
    'light' para mensagens simples/conversacionais.

    Regras:
    - Mensagens longas (>200 chars) → heavy
    - Contém code blocks ou padrões de código → heavy
    - Contém palavras-chave técnicas → heavy
    - Mensagens curtas sem contexto técnico → light
    """
    text = message.strip()

    # Mensagens longas indicam complexidade
    if len(text) > 200:
        return "heavy"

    # Verifica padrões de código (antes do check de tamanho)
    for pattern in _CODE_PATTERNS:
        if pattern.search(text):
            return "heavy"

    # Mensagens muito curtas sem padrões de código são light
    if len(text) < 15:
        return "light"

    text_lower = text.lower()

    # Verifica palavras-chave técnicas
    words = set(re.findall(r"\b\w+\b", text_lower))
    if words & _HEAVY_KEYWORDS:
        return "heavy"

    # Múltiplas interrogações ou sentenças → possivelmente complexo
    if text.count("?") > 1 or text.count("\n") > 3:
        return "heavy"

    return "light"


def resolve_model_for_tier(
    model_tier: str,
    light_model: str | None = None,
    heavy_model: str | None = None,
    default_model: str | None = None,
) -> str | None:
    """Resolve modelo baseado no model_tier do step do pipeline.

    Mapeamento:
    - 'fast' → light_model
    - 'powerful' → heavy_model
    - fallback → default_model (ai_model do config)
    """
    if model_tier == "fast" and light_model:
        logger.debug("model_tier=%s → %s", model_tier, light_model)
        return light_model
    if model_tier == "powerful" and heavy_model:
        logger.debug("model_tier=%s → %s", model_tier, heavy_model)
        return heavy_model

    return default_model


def select_model(
    message: str,
    light_model: str | None = None,
    heavy_model: str | None = None,
    default_model: str | None = None,
) -> str | None:
    """Seleciona modelo baseado na complexidade da mensagem.

    Retorna o modelo a usar, ou None se não há roteamento configurado.
    """
    if not light_model or not heavy_model:
        return default_model

    complexity = classify_complexity(message)
    selected = light_model if complexity == "light" else heavy_model

    logger.debug(
        "Model routing: '%s...' → %s → %s",
        message[:40],
        complexity,
        selected,
    )

    return selected
