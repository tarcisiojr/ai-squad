"""Testes para GraphStore — grafo de conhecimento relacional em SQLite."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from src.orchestrator.graph import ENTITY_TYPES, RELATION_TYPES, GraphStore


class TestGraphStoreEntities:
    """Testes de operações com entidades."""

    @pytest.fixture
    def store(self, tmp_path):
        """Cria GraphStore com diretório temporário."""
        s = GraphStore(state_dir=str(tmp_path))
        yield s
        s.close()

    def test_add_entity_nova(self, store):
        """Verifica que uma entidade nova é persistida."""
        eid = store.add_entity("auth-middleware", "module", "Modulo de autenticacao")
        assert eid is not None

        entities, relations = store.count()
        assert entities == 1
        assert relations == 0

    def test_add_entity_duplicata_incrementa_mention(self, store):
        """Verifica que entidade duplicada incrementa mention_count."""
        store.add_entity("auth-middleware", "module", "Descricao 1")
        store.add_entity("auth-middleware", "module", "Descricao 2")

        entities, _ = store.count()
        assert entities == 1

        # Verifica mention_count via stats
        stats = store.stats()
        top = stats["top_entities"]
        assert top[0]["mention_count"] == 2

    def test_add_entity_tipo_invalido_retorna_none(self, store):
        """Verifica que tipo inválido é rejeitado."""
        eid = store.add_entity("teste", "tipo_invalido")
        assert eid is None

        entities, _ = store.count()
        assert entities == 0

    def test_add_entity_nome_vazio_retorna_none(self, store):
        """Verifica que nome vazio é rejeitado."""
        eid = store.add_entity("", "module")
        assert eid is None

    def test_add_entity_normaliza_nome(self, store):
        """Verifica que nomes são normalizados para lowercase."""
        store.add_entity("Auth-Middleware", "module")
        store.add_entity("auth-middleware", "module")

        entities, _ = store.count()
        assert entities == 1  # Mesmo nome normalizado


class TestGraphStoreRelations:
    """Testes de operações com relações."""

    @pytest.fixture
    def store(self, tmp_path):
        s = GraphStore(state_dir=str(tmp_path))
        yield s
        s.close()

    def test_add_relation_entre_entidades(self, store):
        """Verifica que relação é criada entre entidades existentes."""
        store.add_entity("auth-middleware", "module")
        store.add_entity("session-timeout", "bug")

        ok = store.add_relation(
            "auth-middleware", "module",
            "session-timeout", "bug",
            "affects",
            evidence="auth-middleware causa timeout na sessao",
        )
        assert ok is True

        _, relations = store.count()
        assert relations == 1

    def test_add_relation_reforça_peso(self, store):
        """Verifica que relação duplicada incrementa weight."""
        store.add_entity("auth-middleware", "module")
        store.add_entity("session-timeout", "bug")

        store.add_relation("auth-middleware", "module", "session-timeout", "bug", "affects")
        store.add_relation("auth-middleware", "module", "session-timeout", "bug", "affects")

        _, relations = store.count()
        assert relations == 1  # Mesma relação, não duplica

    def test_add_relation_tipo_invalido(self, store):
        """Verifica que tipo de relação inválido é rejeitado."""
        store.add_entity("a", "module")
        store.add_entity("b", "bug")

        ok = store.add_relation("a", "module", "b", "bug", "tipo_invalido")
        assert ok is False

    def test_add_relation_entidade_inexistente(self, store):
        """Verifica que relação com entidade inexistente falha."""
        store.add_entity("a", "module")

        ok = store.add_relation("a", "module", "nao-existe", "bug", "affects")
        assert ok is False

    def test_reinforce_ajusta_peso(self, store):
        """Verifica que reinforce incrementa peso da relação."""
        store.add_entity("a", "module")
        store.add_entity("b", "bug")
        store.add_relation("a", "module", "b", "bug", "affects")

        ok = store.reinforce("a", "b", delta=5)
        assert ok is True

    def test_reinforce_entidade_inexistente(self, store):
        """Verifica que reinforce com entidade inexistente retorna False."""
        ok = store.reinforce("nao-existe", "tambem-nao", delta=1)
        assert ok is False


class TestGraphStoreTraversal:
    """Testes de traversal via recursive CTE."""

    @pytest.fixture
    def store(self, tmp_path):
        s = GraphStore(state_dir=str(tmp_path))
        # Monta grafo: A → B → C → D
        s.add_entity("a", "module")
        s.add_entity("b", "bug")
        s.add_entity("c", "pattern")
        s.add_entity("d", "technology")
        s.add_relation("a", "module", "b", "bug", "affects")
        s.add_relation("b", "bug", "c", "pattern", "caused_by")
        s.add_relation("c", "pattern", "d", "technology", "depends_on")
        yield s
        s.close()

    def test_traverse_encontra_conectados(self, store):
        """Verifica que traversal encontra entidades conectadas."""
        result = store.traverse("a", depth=3)
        names = {e["name"] for e in result.entities}
        assert "a" in names
        assert "b" in names
        assert len(result.relations) > 0

    def test_traverse_respeita_profundidade(self, store):
        """Verifica que depth=1 limita resultado."""
        result = store.traverse("a", depth=1)
        names = {e["name"] for e in result.entities}
        assert "a" in names
        assert "b" in names
        # c e d não devem estar com depth=1
        assert "d" not in names

    def test_traverse_entidade_inexistente(self, store):
        """Verifica que entidade inexistente retorna vazio."""
        result = store.traverse("nao-existe")
        assert len(result.entities) == 0
        assert len(result.relations) == 0

    def test_traverse_nome_vazio(self, store):
        """Verifica que nome vazio retorna vazio."""
        result = store.traverse("")
        assert len(result.entities) == 0


class TestGraphStoreQuery:
    """Testes de busca FTS5 com expansão por traversal."""

    @pytest.fixture
    def store(self, tmp_path):
        s = GraphStore(state_dir=str(tmp_path))
        s.add_entity("auth-middleware", "module", "Modulo de autenticacao e sessao")
        s.add_entity("session-timeout", "bug", "Bug de timeout na sessao")
        s.add_entity("jwt-library", "technology", "Biblioteca JWT para tokens")
        s.add_relation("auth-middleware", "module", "session-timeout", "bug", "affects")
        s.add_relation("auth-middleware", "module", "jwt-library", "technology", "uses")
        yield s
        s.close()

    def test_query_encontra_por_nome(self, store):
        """Verifica que busca FTS5 encontra entidades por nome."""
        result = store.query("auth-middleware")
        assert len(result.entities) > 0
        names = {e["name"] for e in result.entities}
        assert "auth-middleware" in names

    def test_query_encontra_por_descricao(self, store):
        """Verifica que busca FTS5 encontra entidades por descrição."""
        result = store.query("autenticacao sessao")
        assert len(result.entities) > 0

    def test_query_sem_resultado(self, store):
        """Verifica que busca sem match retorna vazio."""
        result = store.query("xyzabc123")
        assert len(result.entities) == 0

    def test_query_vazio(self, store):
        """Verifica que query vazia retorna vazio."""
        result = store.query("")
        assert len(result.entities) == 0


class TestGraphStorePrune:
    """Testes de pruning automático."""

    @pytest.fixture
    def store(self, tmp_path):
        s = GraphStore(state_dir=str(tmp_path))
        yield s
        s.close()

    def test_prune_remove_relacoes_peso_zero(self, store):
        """Verifica que relações com peso <= 0 são removidas."""
        store.add_entity("a", "module")
        store.add_entity("b", "bug")
        store.add_relation("a", "module", "b", "bug", "affects")

        # Reduz peso para 0
        store.reinforce("a", "b", delta=-1)

        removed = store.prune()
        assert removed > 0

        _, relations = store.count()
        assert relations == 0

    def test_prune_respeita_limites(self, store):
        """Verifica que pruning roda quando MAX_ENTITIES é excedido."""
        original_max = GraphStore.MAX_ENTITIES
        GraphStore.MAX_ENTITIES = 5

        try:
            for i in range(10):
                store.add_entity(f"entidade-{i}", "concept", f"desc {i}")

            store.prune()
            entities, _ = store.count()
            assert entities <= 5
        finally:
            GraphStore.MAX_ENTITIES = original_max


class TestGraphStoreFormatPrompt:
    """Testes de formatação para prompt."""

    @pytest.fixture
    def store(self, tmp_path):
        s = GraphStore(state_dir=str(tmp_path))
        s.add_entity("auth-middleware", "module", "Modulo de autenticacao")
        s.add_entity("session-timeout", "bug", "Bug de timeout")
        s.add_relation("auth-middleware", "module", "session-timeout", "bug", "affects")
        yield s
        s.close()

    def test_format_retorna_markdown(self, store):
        """Verifica que formatação retorna Markdown com entidades e relações."""
        result = store.format_for_prompt("auth middleware")
        assert "Conhecimento relacionado" in result
        assert "auth-middleware" in result

    def test_format_sem_resultado(self, store):
        """Verifica que sem resultados retorna string vazia."""
        result = store.format_for_prompt("xyzabc123")
        assert result == ""


class TestGraphStoreIngest:
    """Testes de ingestão via callback LLM."""

    @pytest.fixture
    def store(self, tmp_path):
        s = GraphStore(state_dir=str(tmp_path))
        yield s
        s.close()

    @pytest.mark.asyncio
    async def test_ingest_extrai_entidades_e_relacoes(self, store):
        """Verifica que ingest chama callback e persiste extração."""
        mock_response = json.dumps({
            "entities": [
                {"name": "auth-middleware", "type": "module", "description": "Modulo auth"},
                {"name": "session-bug", "type": "bug", "description": "Bug de sessao"},
            ],
            "relations": [
                {"from": "auth-middleware", "to": "session-bug", "type": "affects", "evidence": "causa bug"},
            ],
        })
        callback = AsyncMock(return_value=mock_response)
        store.set_extract_callback(callback)

        await store._ingest_async("Bug no auth causou timeout", "demand-001")

        entities, relations = store.count()
        assert entities == 2
        assert relations == 1
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_sem_callback_nao_falha(self, store):
        """Verifica que ingest sem callback retorna silenciosamente."""
        await store.ingest("texto qualquer", "demand-001")
        entities, _ = store.count()
        assert entities == 0

    @pytest.mark.asyncio
    async def test_ingest_json_invalido_nao_falha(self, store):
        """Verifica que JSON inválido é tratado sem erro."""
        callback = AsyncMock(return_value="isto nao e json")
        store.set_extract_callback(callback)

        await store._ingest_async("texto", "demand-001")

        entities, _ = store.count()
        assert entities == 0

    @pytest.mark.asyncio
    async def test_ingest_tipos_invalidos_filtrados(self, store):
        """Verifica que entidades com tipos inválidos são descartadas."""
        mock_response = json.dumps({
            "entities": [
                {"name": "valida", "type": "module", "description": "ok"},
                {"name": "invalida", "type": "tipo_errado", "description": "nao"},
            ],
            "relations": [],
        })
        callback = AsyncMock(return_value=mock_response)
        store.set_extract_callback(callback)

        await store._ingest_async("texto", "demand-001")

        entities, _ = store.count()
        assert entities == 1  # Só a válida

    @pytest.mark.asyncio
    async def test_ingest_callback_falha_nao_interrompe(self, store):
        """Verifica que exceção no callback é logada sem interromper."""
        callback = AsyncMock(side_effect=RuntimeError("LLM indisponivel"))
        store.set_extract_callback(callback)

        # Não deve lançar exceção
        await store._ingest_async("texto", "demand-001")

        entities, _ = store.count()
        assert entities == 0

    @pytest.mark.asyncio
    async def test_ingest_throttle_descarta_chamada_rapida(self, store):
        """Verifica que chamadas rápidas demais são descartadas pelo throttle."""
        callback = AsyncMock(return_value='{"entities":[],"relations":[]}')
        store.set_extract_callback(callback)

        # Primeira chamada: registra timestamp
        await store.ingest("texto 1", "demand-001")
        # Aguarda task criada
        await asyncio.sleep(0.1)

        # Segunda chamada imediata: deve ser descartada pelo throttle
        await store.ingest("texto 2", "demand-001")
        await asyncio.sleep(0.1)

        # Callback deve ter sido chamado apenas 1 vez (primeira ingestão)
        assert callback.call_count == 1


class TestGraphStoreStats:
    """Testes de métricas do grafo."""

    @pytest.fixture
    def store(self, tmp_path):
        s = GraphStore(state_dir=str(tmp_path))
        yield s
        s.close()

    def test_stats_grafo_vazio(self, store):
        """Verifica stats com grafo vazio."""
        stats = store.stats()
        assert stats["entity_count"] == 0
        assert stats["relation_count"] == 0
        assert stats["top_entities"] == []

    def test_stats_com_dados(self, store):
        """Verifica stats com dados."""
        store.add_entity("a", "module")
        store.add_entity("b", "bug")
        store.add_relation("a", "module", "b", "bug", "affects")

        stats = store.stats()
        assert stats["entity_count"] == 2
        assert stats["relation_count"] == 1
        assert len(stats["top_entities"]) == 2


class TestGraphStoreTypes:
    """Testes dos tipos permitidos."""

    def test_entity_types_sao_conhecidos(self):
        """Verifica que todos os tipos de entidade estão definidos."""
        assert "bug" in ENTITY_TYPES
        assert "module" in ENTITY_TYPES
        assert "pattern" in ENTITY_TYPES
        assert "technology" in ENTITY_TYPES
        assert "decision" in ENTITY_TYPES
        assert "agent" in ENTITY_TYPES
        assert "concept" in ENTITY_TYPES
        assert "artifact" in ENTITY_TYPES
        assert "quality" in ENTITY_TYPES

    def test_relation_types_sao_conhecidos(self):
        """Verifica que todos os tipos de relação estão definidos."""
        assert "caused_by" in RELATION_TYPES
        assert "resolved_by" in RELATION_TYPES
        assert "affects" in RELATION_TYPES
        assert "uses" in RELATION_TYPES
        assert "produced" in RELATION_TYPES
        assert "depends_on" in RELATION_TYPES
        assert "related_to" in RELATION_TYPES
        assert "rejected_by" in RELATION_TYPES
        assert "improved_by" in RELATION_TYPES
