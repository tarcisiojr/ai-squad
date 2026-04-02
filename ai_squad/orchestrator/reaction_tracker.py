"""Rastreamento de reações do Telegram para reforço de documentos.

Mapeia message_id → documento da knowledge base usado na resposta.
Quando o usuário reage com 👍 ou 👎, atualiza o score do documento.
"""

import logging
import time
from collections import OrderedDict

logger = logging.getLogger("ai-squad.reactions")

# Emojis e seus deltas de score
REACTION_DELTAS: dict[str, int] = {
    "👍": 1,
    "👎": -1,
    "❤": 2,
    "🔥": 1,
    "😢": -1,
}

# Tempo de expiração do mapeamento (24h em segundos)
MAPPING_TTL = 86400

# Máximo de entries no mapeamento
MAX_MAPPINGS = 10000


class ReactionTracker:
    """Rastreia reações em mensagens do bot e atualiza score dos documentos.

    Mantém mapeamento em memória msg_id → doc_path com LRU e TTL.
    Não persiste entre restarts — aceitável porque reações chegam em minutos.
    """

    def __init__(self, knowledge_store=None) -> None:
        """Inicializa tracker.

        Args:
            knowledge_store: KnowledgeStore para atualizar scores.
                Se None, tracker opera em modo passivo (só loga).
        """
        self._knowledge = knowledge_store
        self._msg_to_doc: OrderedDict[int, tuple[str, float]] = OrderedDict()

    def track(self, msg_id: int, doc_path: str) -> None:
        """Registra qual documento gerou a resposta de msg_id."""
        self._evict_expired()

        # LRU: remove se já existe e readiciona no final
        self._msg_to_doc.pop(msg_id, None)
        self._msg_to_doc[msg_id] = (doc_path, time.time())

        # Respeita limite máximo
        while len(self._msg_to_doc) > MAX_MAPPINGS:
            self._msg_to_doc.popitem(last=False)

        logger.debug("Tracking: msg_id=%d → %s", msg_id, doc_path)

    def on_reaction(self, msg_id: int, emoji: str) -> str | None:
        """Processa reação e atualiza score do documento.

        Returns:
            Path do documento atualizado, ou None se msg_id não mapeado.
        """
        entry = self._msg_to_doc.get(msg_id)
        if not entry:
            logger.debug("Reação ignorada: msg_id=%d sem mapeamento", msg_id)
            return None

        doc_path, _timestamp = entry
        delta = REACTION_DELTAS.get(emoji, 0)
        if delta == 0:
            logger.debug("Emoji não mapeado para score: %s", emoji)
            return None

        if self._knowledge:
            self._knowledge.update_score(doc_path, delta)
            logger.info(
                "Score atualizado: %s (%s%d via %s)",
                doc_path,
                "+" if delta > 0 else "",
                delta,
                emoji,
            )
        else:
            logger.info(
                "Score não atualizado (sem knowledge store): %s %s",
                doc_path,
                emoji,
            )

        return doc_path

    def get_doc_for_msg(self, msg_id: int) -> str | None:
        """Retorna o documento associado a uma mensagem (se existir)."""
        entry = self._msg_to_doc.get(msg_id)
        if entry:
            return entry[0]
        return None

    @property
    def active_mappings(self) -> int:
        """Retorna quantidade de mapeamentos ativos."""
        self._evict_expired()
        return len(self._msg_to_doc)

    def _evict_expired(self) -> None:
        """Remove entries expiradas (mais antigas que TTL)."""
        now = time.time()
        expired = []
        for msg_id, (_doc, timestamp) in self._msg_to_doc.items():
            if now - timestamp > MAPPING_TTL:
                expired.append(msg_id)
            else:
                break  # OrderedDict é ordenado por inserção
        for msg_id in expired:
            del self._msg_to_doc[msg_id]

    def clear(self) -> None:
        """Limpa todos os mapeamentos."""
        self._msg_to_doc.clear()
