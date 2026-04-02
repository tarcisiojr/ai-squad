"""Testes para ReactionTracker — rastreamento de reações para reforço."""

import time
from unittest.mock import MagicMock

import pytest

from ai_squad.orchestrator.reaction_tracker import (
    MAPPING_TTL,
    MAX_MAPPINGS,
    ReactionTracker,
)


class TestReactionTracker:
    """Testes do ReactionTracker."""

    @pytest.fixture
    def tracker(self):
        """Tracker sem knowledge store (modo passivo)."""
        return ReactionTracker()

    @pytest.fixture
    def tracker_with_kb(self):
        """Tracker com knowledge store mockado."""
        kb = MagicMock()
        return ReactionTracker(knowledge_store=kb), kb

    def test_track_registra_mapeamento(self, tracker):
        """Verifica que track registra msg_id → doc_path."""
        tracker.track(123, "atendimentos/vpn.md")
        assert tracker.get_doc_for_msg(123) == "atendimentos/vpn.md"

    def test_track_sobrescreve_existente(self, tracker):
        """Verifica que track atualiza se msg_id já existe."""
        tracker.track(123, "doc1.md")
        tracker.track(123, "doc2.md")
        assert tracker.get_doc_for_msg(123) == "doc2.md"
        assert tracker.active_mappings == 1

    def test_on_reaction_positiva_retorna_doc(self, tracker):
        """Verifica que reação 👍 retorna o doc path."""
        tracker.track(100, "atendimentos/vpn.md")
        result = tracker.on_reaction(100, "👍")
        assert result == "atendimentos/vpn.md"

    def test_on_reaction_negativa_retorna_doc(self, tracker):
        """Verifica que reação 👎 retorna o doc path."""
        tracker.track(100, "atendimentos/vpn.md")
        result = tracker.on_reaction(100, "👎")
        assert result == "atendimentos/vpn.md"

    def test_on_reaction_sem_mapeamento_retorna_none(self, tracker):
        """Verifica que reação sem mapeamento é ignorada."""
        result = tracker.on_reaction(999, "👍")
        assert result is None

    def test_on_reaction_emoji_desconhecido_retorna_none(self, tracker):
        """Verifica que emoji não mapeado retorna None."""
        tracker.track(100, "doc.md")
        result = tracker.on_reaction(100, "🤷")
        assert result is None

    def test_on_reaction_atualiza_score_no_kb(self, tracker_with_kb):
        """Verifica que reação positiva chama update_score no knowledge store."""
        tracker, kb = tracker_with_kb
        tracker.track(100, "atendimentos/vpn.md")
        tracker.on_reaction(100, "👍")
        kb.update_score.assert_called_once_with("atendimentos/vpn.md", 1)

    def test_on_reaction_negativa_decrementa_score(self, tracker_with_kb):
        """Verifica que reação negativa decrementa score."""
        tracker, kb = tracker_with_kb
        tracker.track(100, "doc.md")
        tracker.on_reaction(100, "👎")
        kb.update_score.assert_called_once_with("doc.md", -1)

    def test_on_reaction_coracao_incrementa_2(self, tracker_with_kb):
        """Verifica que ❤ incrementa score em 2."""
        tracker, kb = tracker_with_kb
        tracker.track(100, "doc.md")
        tracker.on_reaction(100, "❤")
        kb.update_score.assert_called_once_with("doc.md", 2)

    def test_lru_respeita_limite_maximo(self, tracker):
        """Verifica que LRU respeita MAX_MAPPINGS."""
        for i in range(MAX_MAPPINGS + 100):
            tracker.track(i, f"doc-{i}.md")
        assert tracker.active_mappings <= MAX_MAPPINGS

    def test_expiracao_por_ttl(self, tracker):
        """Verifica que entries expiram após TTL."""
        tracker.track(100, "doc.md")

        # Simula entry expirada manipulando timestamp
        tracker._msg_to_doc[100] = ("doc.md", time.time() - MAPPING_TTL - 1)

        assert tracker.get_doc_for_msg(100) is not None  # Ainda no dict
        # Após evict, deve sumir
        tracker._evict_expired()
        assert 100 not in tracker._msg_to_doc

    def test_clear_limpa_tudo(self, tracker):
        """Verifica que clear remove todos os mapeamentos."""
        tracker.track(1, "doc1.md")
        tracker.track(2, "doc2.md")
        tracker.clear()
        assert tracker.active_mappings == 0

    def test_active_mappings_conta_corretamente(self, tracker):
        """Verifica contagem de mapeamentos ativos."""
        assert tracker.active_mappings == 0
        tracker.track(1, "doc1.md")
        assert tracker.active_mappings == 1
        tracker.track(2, "doc2.md")
        assert tracker.active_mappings == 2
