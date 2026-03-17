"""Testes para LessonsStore — persistência de lições aprendidas com FTS5."""

import json
from datetime import datetime, timezone

import pytest

from src.orchestrator.lessons import LessonsStore


class TestLessonsStore:
    """Testes de operações básicas do LessonsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Cria LessonsStore com diretório temporário."""
        s = LessonsStore(state_dir=str(tmp_path))
        yield s
        s.close()

    def test_add_licao_armazenada(self, store):
        """Verifica que uma lição adicionada é persistida corretamente."""
        store.add(
            category="deploy",
            problem="Container falhou por falta de permissão",
            solution="Adicionar USER agent antes de instalar dependências",
            agent_name="dev-backend",
            demand_id="demand-001",
        )

        assert store.count() == 1
        licoes = store.get_relevant()
        assert len(licoes) == 1
        assert licoes[0]["category"] == "deploy"
        assert licoes[0]["problem"] == "Container falhou por falta de permissão"
        assert licoes[0]["solution"] == "Adicionar USER agent antes de instalar dependências"
        assert licoes[0]["agent_name"] == "dev-backend"
        assert licoes[0]["demand_id"] == "demand-001"
        assert licoes[0]["used_count"] == 0

    def test_add_respeita_limite_max_lessons(self, store):
        """Verifica que ao ultrapassar MAX_LESSONS as mais antigas/menos usadas são removidas."""
        # Adiciona MAX_LESSONS + 5 lições
        for i in range(LessonsStore.MAX_LESSONS + 5):
            store.add(
                category=f"cat-{i}",
                problem=f"problema {i}",
                solution=f"solução {i}",
            )

        assert store.count() == LessonsStore.MAX_LESSONS

    def test_add_evicta_menos_usadas_primeiro(self, store):
        """Verifica que a evição prioriza lições com menor used_count."""
        # Adiciona MAX_LESSONS lições
        for i in range(LessonsStore.MAX_LESSONS):
            store.add(
                category="base",
                problem=f"problema {i}",
                solution=f"solução {i}",
            )

        # Incrementa used_count da primeira lição para protegê-la da evição
        conn = store._get_conn()
        conn.execute("UPDATE lessons SET used_count = 100 WHERE id = 1")
        conn.commit()

        # Adiciona mais uma para forçar evição
        store.add(
            category="nova",
            problem="problema novo",
            solution="solução nova",
        )

        assert store.count() == LessonsStore.MAX_LESSONS

        # A lição com used_count=100 deve sobreviver
        row = conn.execute("SELECT * FROM lessons WHERE id = 1").fetchone()
        assert row is not None
        assert row["used_count"] == 100

    def test_count_retorna_total_correto(self, store):
        """Verifica que count() retorna a quantidade correta de lições."""
        assert store.count() == 0

        store.add("cat", "prob1", "sol1")
        assert store.count() == 1

        store.add("cat", "prob2", "sol2")
        assert store.count() == 2

    def test_close_fecha_conexao(self, store):
        """Verifica que close() fecha a conexão e permite reabrir."""
        store.add("cat", "prob", "sol")
        store.close()

        assert store._conn is None

    def test_close_duplo_nao_falha(self, store):
        """Verifica que chamar close() duas vezes não causa erro."""
        store.close()
        store.close()
        assert store._conn is None


class TestLessonsFTS:
    """Testes de busca full-text (FTS5) do LessonsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Cria LessonsStore com lições pré-populadas para busca."""
        s = LessonsStore(state_dir=str(tmp_path))
        s.add("deploy", "Docker container sem rede", "Habilitar networking no compose", agent_name="dev-backend")
        s.add("frontend", "React componente não renderiza", "Verificar export default", agent_name="dev-frontend")
        s.add("testes", "Coverage abaixo do mínimo", "Adicionar testes unitários para módulo X", agent_name="qa")
        s.add("api", "Endpoint retornando 500", "Corrigir validação de payload", agent_name="dev-backend")
        s.add("database", "Migração falhou no PostgreSQL", "Usar transação explícita no schema", agent_name="dev-backend")
        yield s
        s.close()

    def test_get_relevant_sem_contexto_retorna_recentes(self, store):
        """Verifica que sem contexto retorna as lições mais recentes."""
        licoes = store.get_relevant()
        assert len(licoes) == 5
        # A mais recente deve ser a última adicionada (database)
        assert licoes[0]["category"] == "database"

    def test_get_relevant_contexto_vazio_retorna_recentes(self, store):
        """Verifica que contexto vazio ou só espaços retorna recentes."""
        licoes_vazio = store.get_relevant("")
        licoes_espacos = store.get_relevant("   ")
        assert len(licoes_vazio) == 5
        assert len(licoes_espacos) == 5

    def test_get_relevant_com_contexto_usa_fts5(self, store):
        """Verifica que contexto textual busca via FTS5 e encontra resultados relevantes."""
        licoes = store.get_relevant("Docker container")
        assert len(licoes) >= 1
        # Deve encontrar a lição sobre Docker
        categorias = [l["category"] for l in licoes]
        assert "deploy" in categorias

    def test_get_relevant_contexto_sem_match_retorna_recentes(self, store):
        """Verifica que contexto sem match FTS5 faz fallback para recentes."""
        licoes = store.get_relevant("xyzzyplugh inexistente")
        # Deve retornar recentes como fallback
        assert len(licoes) >= 1

    def test_get_relevant_contexto_palavras_curtas_ignoradas(self, store):
        """Verifica que palavras com menos de 3 caracteres são ignoradas na busca."""
        # Apenas palavras curtas — deve fazer fallback para recentes
        licoes = store.get_relevant("a b cd")
        assert len(licoes) == 5

    def test_get_relevant_respeita_limite_max_context(self, tmp_path):
        """Verifica que get_relevant nunca retorna mais que MAX_CONTEXT_LESSONS."""
        store = LessonsStore(state_dir=str(tmp_path))
        # Adiciona 15 lições com a mesma palavra para FTS5 encontrar todas
        for i in range(15):
            store.add("infraestrutura", f"servidor caiu cenário {i}", f"solução {i}")

        licoes = store.get_relevant("servidor infraestrutura")
        assert len(licoes) <= LessonsStore.MAX_CONTEXT_LESSONS
        store.close()

    def test_get_relevant_query_fts_invalida_fallback(self, store):
        """Verifica que query FTS5 inválida faz fallback para recentes."""
        # Caracteres especiais que podem causar erro no FTS5
        licoes = store.get_relevant('NOT AND OR "unclosed quote')
        assert len(licoes) >= 1

    def test_fts5_indexa_multiplas_licoes(self, store):
        """Verifica que FTS5 indexa corretamente múltiplas lições para busca."""
        # Busca por termo que aparece apenas na lição de frontend
        licoes = store.get_relevant("React componente renderiza")
        categorias = [l["category"] for l in licoes]
        assert "frontend" in categorias

        # Busca por termo que aparece apenas na lição de database
        licoes = store.get_relevant("PostgreSQL migração schema")
        categorias = [l["category"] for l in licoes]
        assert "database" in categorias

    def test_fts5_busca_por_agent_name(self, store):
        """Verifica que FTS5 também indexa agent_name para busca."""
        licoes = store.get_relevant("dev-frontend")
        # Deve encontrar a lição do dev-frontend (o traço é separador em unicode61)
        assert len(licoes) >= 1


class TestLessonsFormatPrompt:
    """Testes de formatação para prompt e marcação de uso."""

    @pytest.fixture
    def store(self, tmp_path):
        """Cria LessonsStore com lições para formatação."""
        s = LessonsStore(state_dir=str(tmp_path))
        yield s
        s.close()

    def test_format_for_prompt_vazio(self, store):
        """Verifica que format_for_prompt retorna string vazia quando não há lições."""
        resultado = store.format_for_prompt()
        assert resultado == ""

    def test_format_for_prompt_formata_corretamente(self, store):
        """Verifica que format_for_prompt gera o formato correto para injeção."""
        store.add("deploy", "Faltou variável de ambiente", "Adicionar ao .env", agent_name="dev-backend")
        store.add("testes", "Teste flaky por timing", "Usar mock de tempo")

        resultado = store.format_for_prompt()

        assert "## Licoes aprendidas (evite repetir erros)" in resultado
        assert "**deploy** (dev-backend):" in resultado
        assert "Faltou variável de ambiente" in resultado
        assert "→ Adicionar ao .env" in resultado
        # Lição sem agent_name não deve ter parênteses vazios
        assert "**testes**:" in resultado
        assert "()" not in resultado

    def test_format_for_prompt_incrementa_used_count(self, store):
        """Verifica que format_for_prompt incrementa used_count das lições retornadas."""
        store.add("cat", "problema", "solução")

        # Antes de formatar
        licoes = store.get_relevant()
        assert licoes[0]["used_count"] == 0

        # Formata (deve incrementar)
        store.format_for_prompt()

        # Depois de formatar
        licoes = store.get_relevant()
        assert licoes[0]["used_count"] == 1

    def test_format_for_prompt_incrementa_multiplas_vezes(self, store):
        """Verifica que múltiplas chamadas incrementam used_count acumulativamente."""
        store.add("cat", "problema", "solução")

        store.format_for_prompt()
        store.format_for_prompt()
        store.format_for_prompt()

        licoes = store.get_relevant()
        assert licoes[0]["used_count"] == 3

    def test_format_for_prompt_com_contexto(self, store):
        """Verifica que format_for_prompt aceita contexto para filtrar lições."""
        store.add("docker", "Container sem memória", "Aumentar limits", agent_name="ops")
        store.add("python", "Import circular", "Reorganizar módulos", agent_name="dev")

        resultado = store.format_for_prompt(context="docker container")
        assert "## Licoes aprendidas" in resultado


class TestLessonsMigration:
    """Testes de migração de JSON legado para SQLite."""

    def test_migrate_from_json(self, tmp_path):
        """Verifica que lessons.json é migrado corretamente para SQLite."""
        # Cria arquivo JSON legado
        lessons_json = [
            {
                "category": "deploy",
                "problem": "Problema legado 1",
                "solution": "Solução legada 1",
                "agent_name": "dev-backend",
                "demand_id": "demand-old-1",
                "timestamp": "2025-01-01T00:00:00+00:00",
                "used_count": 3,
            },
            {
                "category": "testes",
                "problem": "Problema legado 2",
                "solution": "Solução legada 2",
                "agent_name": "",
                "demand_id": "",
                "timestamp": "2025-01-02T00:00:00+00:00",
                "used_count": 0,
            },
        ]
        json_path = tmp_path / "lessons.json"
        json_path.write_text(json.dumps(lessons_json), encoding="utf-8")

        # Cria store — deve migrar automaticamente
        store = LessonsStore(state_dir=str(tmp_path))

        assert store.count() == 2

        # Verifica dados migrados
        licoes = store.get_relevant()
        categorias = [l["category"] for l in licoes]
        assert "deploy" in categorias
        assert "testes" in categorias

        # Verifica que JSON foi renomeado para .migrated
        assert not json_path.exists()
        assert (tmp_path / "lessons.json.migrated").exists()

        store.close()

    def test_migrate_pula_se_ja_migrado(self, tmp_path):
        """Verifica que migração não duplica dados se já existem lições no banco."""
        # Cria store e adiciona lição diretamente
        store = LessonsStore(state_dir=str(tmp_path))
        store.add("existente", "já existe", "solução existente")
        store.close()

        # Cria arquivo JSON (simula cenário onde JSON aparece depois)
        lessons_json = [
            {"category": "nova", "problem": "do json", "solution": "sol json"}
        ]
        json_path = tmp_path / "lessons.json"
        json_path.write_text(json.dumps(lessons_json), encoding="utf-8")

        # Reabre store — deve detectar que já tem dados e pular migração
        store2 = LessonsStore(state_dir=str(tmp_path))
        assert store2.count() == 1  # Não duplicou
        assert not json_path.exists()  # JSON removido

        store2.close()

    def test_migrate_json_vazio(self, tmp_path):
        """Verifica que JSON vazio é removido sem erro."""
        json_path = tmp_path / "lessons.json"
        json_path.write_text("[]", encoding="utf-8")

        store = LessonsStore(state_dir=str(tmp_path))
        assert store.count() == 0
        assert not json_path.exists()  # Removido

        store.close()

    def test_migrate_json_inexistente(self, tmp_path):
        """Verifica que sem lessons.json a migração é ignorada silenciosamente."""
        store = LessonsStore(state_dir=str(tmp_path))
        assert store.count() == 0
        store.close()

    def test_migrate_json_com_campos_faltando(self, tmp_path):
        """Verifica que lições JSON com campos faltando usam defaults."""
        lessons_json = [
            {"category": "parcial", "problem": "só tem 2 campos", "solution": "usa default"}
        ]
        json_path = tmp_path / "lessons.json"
        json_path.write_text(json.dumps(lessons_json), encoding="utf-8")

        store = LessonsStore(state_dir=str(tmp_path))
        assert store.count() == 1

        licoes = store.get_relevant()
        assert licoes[0]["agent_name"] == ""
        assert licoes[0]["demand_id"] == ""
        assert licoes[0]["used_count"] == 0

        store.close()
