"""Testes para KnowledgeStore — busca plugável em base de conhecimento."""

import pytest

from src.orchestrator.knowledge import (
    FTS5Backend,
    KnowledgeStore,
    _extract_title,
    parse_frontmatter,
    update_frontmatter,
)

# --- Testes de utilidades ---


class TestFrontmatter:
    """Testes de parsing e atualização de frontmatter."""

    def test_parse_com_frontmatter(self):
        """Verifica extração de frontmatter YAML."""
        content = "---\nscore: 5\ntags: [vpn, rede]\n---\n# Título\n\nConteúdo"
        meta, body = parse_frontmatter(content)
        assert meta["score"] == 5
        assert meta["tags"] == ["vpn", "rede"]
        assert body.startswith("# Título")

    def test_parse_sem_frontmatter(self):
        """Verifica que documento sem frontmatter retorna meta vazio."""
        content = "# Apenas conteúdo\n\nSem frontmatter"
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_parse_frontmatter_invalido(self):
        """Verifica que frontmatter YAML inválido retorna meta vazio."""
        content = "---\n: invalid: [yaml\n---\n# Conteúdo"
        meta, body = parse_frontmatter(content)
        assert meta == {}

    def test_update_frontmatter_existente(self):
        """Verifica atualização de campo existente no frontmatter."""
        content = "---\nscore: 5\ntags: [vpn]\n---\n# Título"
        updated = update_frontmatter(content, {"score": 6})
        meta, _ = parse_frontmatter(updated)
        assert meta["score"] == 6
        assert meta["tags"] == ["vpn"]

    def test_update_frontmatter_novo_campo(self):
        """Verifica adição de campo novo no frontmatter."""
        content = "---\nscore: 0\n---\n# Título"
        updated = update_frontmatter(content, {"tags": ["novo"]})
        meta, _ = parse_frontmatter(updated)
        assert meta["tags"] == ["novo"]
        assert meta["score"] == 0

    def test_update_frontmatter_sem_frontmatter_cria(self):
        """Verifica que documentos sem frontmatter ganham um."""
        content = "# Só conteúdo"
        updated = update_frontmatter(content, {"score": 1})
        meta, body = parse_frontmatter(updated)
        assert meta["score"] == 1
        assert "Só conteúdo" in body

    def test_extract_title_com_heading(self):
        """Verifica extração de título do primeiro heading."""
        assert _extract_title("# Meu Título\n\nConteúdo") == "Meu Título"

    def test_extract_title_sem_heading(self):
        """Verifica que retorna vazio quando não há heading."""
        assert _extract_title("Sem heading\nApenas texto") == ""


# --- Testes FTS5Backend ---


class TestFTS5Backend:
    """Testes do backend FTS5."""

    @pytest.fixture
    def kb_dir(self, tmp_path):
        """Cria diretório de knowledge base com documentos de teste."""
        kb = tmp_path / "knowledge"
        kb.mkdir()
        atendimentos = kb / "atendimentos"
        atendimentos.mkdir()

        # Documento com frontmatter
        (atendimentos / "vpn-nao-conecta.md").write_text(
            "---\nscore: 5\ntags: [vpn, rede, forticlient]\n---\n"
            "# VPN não conecta\n\n"
            "## Problema\nUsuário reporta que VPN parou de funcionar.\n\n"
            "## Solução\n1. Reiniciar serviço FortiClient\n2. Limpar cache DNS\n",
            encoding="utf-8",
        )

        # Documento sem frontmatter
        (atendimentos / "email-lento.md").write_text(
            "# Email Outlook lento\n\n"
            "## Problema\nOutlook demora 30s para abrir.\n\n"
            "## Solução\nLimpar cache do Outlook e recriar perfil.\n",
            encoding="utf-8",
        )

        # Documento de documentação
        docs = kb / "documentacao" / "sistemas"
        docs.mkdir(parents=True)
        (docs / "crm-guia.md").write_text(
            "---\nscore: 2\ntags: [crm, sistema, vendas]\n---\n"
            "# Guia do CRM\n\n"
            "O CRM é o sistema de gestão de clientes.\n"
            "Para acessar: crm.empresa.com\n",
            encoding="utf-8",
        )

        return kb

    @pytest.fixture
    def backend(self, kb_dir):
        """Cria FTS5Backend com documentos indexados."""
        b = FTS5Backend(kb_dir)
        b.reindex_all()
        yield b
        b.close()

    def test_reindex_all_indexa_documentos(self, backend):
        """Verifica que reindex_all encontra e indexa todos os .md."""
        assert backend.count() == 3

    def test_search_encontra_por_termo(self, backend):
        """Verifica busca por termo relevante."""
        results = backend.search("VPN conecta")
        assert len(results) >= 1
        paths = [r.path for r in results]
        assert any("vpn" in p for p in paths)

    def test_search_retorna_snippet(self, backend):
        """Verifica que resultado inclui snippet do conteúdo."""
        results = backend.search("VPN")
        assert len(results) >= 1
        assert results[0].snippet  # Não vazio

    def test_search_boost_por_score(self, backend):
        """Verifica que score é retornado corretamente nos resultados."""
        results = backend.search("VPN rede")
        assert len(results) >= 1
        # O documento de VPN deve ter score 5 (do frontmatter)
        vpn_results = [r for r in results if "vpn" in r.path]
        assert len(vpn_results) >= 1
        assert vpn_results[0].score == 5

    def test_search_sem_query_retorna_vazio(self, backend):
        """Verifica que busca sem query retorna lista vazia."""
        assert backend.search("") == []
        assert backend.search("   ") == []

    def test_search_sem_match_retorna_vazio(self, backend):
        """Verifica que busca sem resultados retorna lista vazia."""
        results = backend.search("xyzzyplugh inexistente")
        assert results == []

    def test_search_palavras_curtas_ignoradas(self, backend):
        """Verifica que palavras menores que 3 caracteres são ignoradas."""
        results = backend.search("a b cd")
        assert results == []

    def test_index_incremental_pula_inalterado(self, kb_dir):
        """Verifica que indexação incremental pula docs não modificados."""
        backend = FTS5Backend(kb_dir)
        doc = kb_dir / "atendimentos" / "vpn-nao-conecta.md"

        backend.index(doc)
        assert backend.count() == 1

        # Indexar de novo — deve pular (hash igual)
        backend.index(doc)
        assert backend.count() == 1

        backend.close()

    def test_index_atualiza_quando_conteudo_muda(self, kb_dir):
        """Verifica que re-indexação atualiza quando conteúdo muda."""
        backend = FTS5Backend(kb_dir)
        doc = kb_dir / "atendimentos" / "vpn-nao-conecta.md"

        backend.index(doc)
        assert backend.count() == 1

        # Modifica conteúdo
        doc.write_text(
            "---\nscore: 10\n---\n# VPN atualizado\n\nNovo conteúdo.",
            encoding="utf-8",
        )
        backend.index(doc)
        assert backend.count() == 1  # Mesmo doc, atualizado

        results = backend.search("atualizado")
        assert len(results) >= 1

        backend.close()

    def test_update_score_incrementa(self, backend, kb_dir):
        """Verifica que update_score incrementa score no banco e no arquivo."""
        rel_path = "atendimentos/vpn-nao-conecta.md"
        backend.update_score(rel_path, 1)

        results = backend.search("VPN")
        assert results[0].score == 6  # Era 5, agora 6

        # Verifica frontmatter do arquivo
        content = (kb_dir / rel_path).read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)
        assert meta["score"] == 6

    def test_update_score_nao_vai_abaixo_de_zero(self, backend):
        """Verifica que score nunca fica negativo."""
        rel_path = "atendimentos/email-lento.md"
        backend.update_score(rel_path, -10)  # Email não tem score (0)

        results = backend.search("Outlook email")
        for r in results:
            if "email" in r.path:
                assert r.score >= 0

    def test_increment_used(self, backend):
        """Verifica que increment_used incrementa o contador."""
        rel_path = "atendimentos/vpn-nao-conecta.md"
        backend.increment_used(rel_path)
        backend.increment_used(rel_path)

        conn = backend._get_conn()
        row = conn.execute(
            "SELECT used_count FROM documents WHERE path = ?",
            (rel_path,),
        ).fetchone()
        assert row["used_count"] == 2

    def test_remove_documento(self, backend):
        """Verifica que remove exclui documento do índice."""
        assert backend.count() == 3
        backend.remove(backend._knowledge_dir / "atendimentos" / "email-lento.md")
        assert backend.count() == 2

    def test_close_fecha_conexao(self, backend):
        """Verifica que close fecha a conexão."""
        backend.close()
        assert backend._conn is None


# --- Testes KnowledgeStore (facade) ---


class TestKnowledgeStore:
    """Testes da facade KnowledgeStore."""

    @pytest.fixture
    def kb_dir(self, tmp_path):
        """Cria diretório com documentos de teste."""
        kb = tmp_path / "knowledge"
        kb.mkdir()
        atendimentos = kb / "atendimentos"
        atendimentos.mkdir()

        (atendimentos / "reset-senha.md").write_text(
            "---\nscore: 3\ntags: [senha, acesso]\n---\n"
            "# Reset de senha\n\n"
            "## Problema\nUsuário esqueceu a senha.\n\n"
            "## Solução\nAcessar portal de autoatendimento e clicar em 'Esqueci minha senha'.\n",
            encoding="utf-8",
        )

        (atendimentos / "wifi-nao-conecta.md").write_text(
            "---\nscore: 7\ntags: [wifi, rede]\n---\n"
            "# WiFi não conecta\n\n"
            "## Problema\nNotebook não conecta na rede corporativa.\n\n"
            "## Solução\nEsquecer rede, reconectar com credenciais AD.\n",
            encoding="utf-8",
        )

        return kb

    @pytest.fixture
    def store(self, kb_dir):
        """Cria KnowledgeStore com FTS5 (padrão)."""
        s = KnowledgeStore(kb_dir)
        s.reindex_all()
        yield s
        s.close()

    def test_search_retorna_resultados(self, store):
        """Verifica busca básica."""
        results = store.search("senha reset")
        assert len(results) >= 1

    def test_format_for_prompt_com_resultados(self, store):
        """Verifica formatação para prompt com resultados."""
        resultado = store.format_for_prompt("wifi rede")
        assert "## Documentos relevantes da base de conhecimento" in resultado
        assert "WiFi" in resultado

    def test_format_for_prompt_sem_resultados(self, store):
        """Verifica que sem resultados retorna string vazia."""
        resultado = store.format_for_prompt("xyzzy inexistente")
        assert resultado == ""

    def test_update_score_via_facade(self, store, kb_dir):
        """Verifica update_score pela facade."""
        store.update_score("atendimentos/reset-senha.md", 2)
        results = store.search("senha")
        for r in results:
            if "reset" in r.path:
                assert r.score == 5  # Era 3, +2

    def test_count_retorna_total(self, store):
        """Verifica contagem de documentos."""
        assert store.count() == 2

    def test_index_novo_documento(self, store, kb_dir):
        """Verifica indexação de novo documento."""
        novo = kb_dir / "atendimentos" / "impressora.md"
        novo.write_text(
            "---\nscore: 0\n---\n# Impressora não imprime\n\nVerificar fila de impressão.\n",
            encoding="utf-8",
        )
        store.index(novo)
        assert store.count() == 3

        results = store.search("impressora imprime")
        assert len(results) >= 1

    def test_fallback_fts5_quando_qmd_indisponivel(self, kb_dir, monkeypatch):
        """Verifica que use_qmd=True faz fallback para FTS5 quando qmd não está instalado."""
        # Simula qmd não instalado para evitar subprocess lento
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        store = KnowledgeStore(kb_dir, use_qmd=True)
        # Deve funcionar mesmo sem qmd (fallback FTS5)
        store.reindex_all()
        assert store.count() >= 0
        store.close()
