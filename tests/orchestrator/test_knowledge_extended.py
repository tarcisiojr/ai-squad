"""Testes adicionais para KnowledgeStore — caminhos não cobertos."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_squad.orchestrator.knowledge import (
    FTS5Backend,
    KnowledgeStore,
    QmdBackend,
    _content_hash,
    _extract_title,
    parse_frontmatter,
    update_frontmatter,
)


class TestContentHash:
    """Testes para _content_hash."""

    def test_hash_determinístico(self):
        """Mesmo texto produz mesmo hash."""
        assert _content_hash("hello") == _content_hash("hello")

    def test_hash_diferente_para_textos_diferentes(self):
        """Textos diferentes produzem hashes diferentes."""
        assert _content_hash("hello") != _content_hash("world")

    def test_hash_comprimento(self):
        """Hash tem 12 caracteres."""
        assert len(_content_hash("qualquer texto")) == 12


class TestFTS5BackendEdgeCases:
    """Testes para caminhos não cobertos do FTS5Backend."""

    @pytest.fixture
    def kb_dir(self, tmp_path):
        kb = tmp_path / "kb"
        kb.mkdir()
        return kb

    @pytest.fixture
    def backend(self, kb_dir):
        b = FTS5Backend(kb_dir)
        yield b
        b.close()

    def test_index_arquivo_inexistente(self, backend, kb_dir):
        """Indexar arquivo inexistente não causa erro."""
        backend.index(kb_dir / "nao-existe.md")
        assert backend.count() == 0

    def test_index_arquivo_com_tags_string(self, backend, kb_dir):
        """Tags como string (não lista) são tratadas corretamente."""
        doc = kb_dir / "doc.md"
        doc.write_text(
            "---\ntags: 'tag-unica'\nscore: 0\n---\n# Doc\n\nConteúdo.",
            encoding="utf-8",
        )
        backend.index(doc)
        assert backend.count() == 1

    def test_index_arquivo_sem_frontmatter(self, backend, kb_dir):
        """Arquivo sem frontmatter é indexado com defaults."""
        doc = kb_dir / "simples.md"
        doc.write_text("# Simples\n\nTexto puro.", encoding="utf-8")
        backend.index(doc)

        results = backend.search("simples texto")
        assert len(results) >= 1

    def test_search_query_com_caracteres_especiais(self, backend, kb_dir):
        """Query com caracteres especiais não causa erro."""
        doc = kb_dir / "doc.md"
        doc.write_text("# Documento\n\nConteúdo normal.", encoding="utf-8")
        backend.index(doc)

        # Não deve lançar exceção
        results = backend.search("!@#$ \"quotes\" 'single'")
        assert isinstance(results, list)

    def test_search_limit(self, backend, kb_dir):
        """Limit restringe número de resultados."""
        for i in range(5):
            doc = kb_dir / f"doc{i}.md"
            doc.write_text(f"# Documento {i}\n\nConteúdo sobre busca.", encoding="utf-8")
            backend.index(doc)

        results = backend.search("busca documento", limit=2)
        assert len(results) <= 2

    def test_update_score_doc_inexistente(self, backend):
        """update_score com documento inexistente não causa erro."""
        backend.update_score("nao/existe.md", 5)
        # Não deve lançar exceção

    def test_update_score_arquivo_nao_existe_no_disco(self, backend, kb_dir):
        """update_score com doc no banco mas sem arquivo no disco."""
        doc = kb_dir / "temp.md"
        doc.write_text("---\nscore: 0\n---\n# Temp\n\nTexto.", encoding="utf-8")
        backend.index(doc)

        # Remove arquivo do disco mas mantém no banco
        doc.unlink()

        # Não deve lançar exceção
        backend.update_score("temp.md", 1)

    def test_remove_com_caminho_absoluto(self, backend, kb_dir):
        """remove com caminho que não é relativo ao kb_dir."""
        doc = kb_dir / "doc.md"
        doc.write_text("# Doc\n\nTexto.", encoding="utf-8")
        backend.index(doc)
        assert backend.count() == 1

        # Passa caminho que não é relativo
        backend.remove(Path("/caminho/absoluto/qualquer.md"))
        # Não deve lançar exceção

    def test_close_idempotente(self, kb_dir):
        """Fechar conexão duas vezes não causa erro."""
        b = FTS5Backend(kb_dir)
        b.close()
        b.close()
        assert b._conn is None

    def test_reindex_all_limpa_e_reindexa(self, backend, kb_dir):
        """reindex_all limpa tudo e reindexa."""
        doc = kb_dir / "doc.md"
        doc.write_text("# Doc\n\nTexto.", encoding="utf-8")
        backend.index(doc)
        assert backend.count() == 1

        # Adiciona outro
        doc2 = kb_dir / "doc2.md"
        doc2.write_text("# Doc2\n\nTexto2.", encoding="utf-8")

        backend.reindex_all()
        assert backend.count() == 2

    def test_index_arquivo_com_erro_leitura(self, backend, kb_dir):
        """Arquivo com erro de leitura é ignorado."""
        doc = kb_dir / "binario.md"
        doc.write_bytes(b"\xff\xfe" + b"\x00" * 100)

        # Não deve lançar exceção
        backend.index(doc)


class TestQmdBackendEdgeCases:
    """Testes para QmdBackend — mocka subprocess."""

    @pytest.fixture
    def kb_dir(self, tmp_path):
        kb = tmp_path / "kb_qmd"
        kb.mkdir()
        return kb

    def test_init_collection_name(self, kb_dir):
        """Collection name é gerada a partir do diretório."""
        backend = QmdBackend(kb_dir)
        assert backend._collection_name.startswith("kb-")

    def test_search_vazio(self, kb_dir):
        """Busca vazia retorna lista vazia."""
        backend = QmdBackend(kb_dir)
        assert backend.search("") == []
        assert backend.search("   ") == []

    @patch("subprocess.run")
    def test_ensure_collection_timeout(self, mock_run, kb_dir):
        """Timeout na inicialização é tratado."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="qmd", timeout=30)

        backend = QmdBackend(kb_dir)
        backend._ensure_collection()
        assert not backend._initialized

    @patch("subprocess.run")
    def test_ensure_collection_not_found(self, mock_run, kb_dir):
        """qmd não instalado é tratado."""
        mock_run.side_effect = FileNotFoundError("qmd not found")

        backend = QmdBackend(kb_dir)
        backend._ensure_collection()
        assert not backend._initialized

    @patch("subprocess.run")
    def test_index_com_embeddings_ok(self, mock_run, kb_dir):
        """Indexação com embeddings disponíveis."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        backend = QmdBackend(kb_dir)
        backend._initialized = True  # Pula ensure_collection

        doc = kb_dir / "doc.md"
        doc.write_text("# Doc\n\nTexto.", encoding="utf-8")
        backend.index(doc)

        assert backend._has_embeddings is True

    @patch("subprocess.run")
    def test_index_sem_embeddings(self, mock_run, kb_dir):
        """Indexação quando embeddings falham."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # update ok
                result.returncode = 0
            else:
                # embed falha
                result.returncode = 1
                result.stderr = "sqlite-vec not available"
            return result

        mock_run.side_effect = side_effect

        backend = QmdBackend(kb_dir)
        backend._initialized = True

        doc = kb_dir / "doc.md"
        doc.write_text("# Doc\n\nTexto.", encoding="utf-8")
        backend.index(doc)

        assert backend._has_embeddings is False

    @patch("subprocess.run")
    def test_check_embeddings_cached(self, mock_run, kb_dir):
        """Resultado de check_embeddings é cacheado."""
        backend = QmdBackend(kb_dir)
        backend._has_embeddings = True

        result = backend._check_embeddings()
        assert result is True
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_check_embeddings_pending_zero(self, mock_run, kb_dir):
        """check_embeddings com Pending: 0 retorna True."""
        mock_result = MagicMock()
        mock_result.stdout = "Status:\n  Pending:  0\n  Vectors: 42"
        mock_run.return_value = mock_result

        backend = QmdBackend(kb_dir)
        result = backend._check_embeddings()
        assert result is True

    @patch("subprocess.run")
    def test_check_embeddings_need_embedding(self, mock_run, kb_dir):
        """check_embeddings com need embedding retorna False."""
        mock_result = MagicMock()
        mock_result.stdout = "Status:\n  3 documents need embedding"
        mock_run.return_value = mock_result

        backend = QmdBackend(kb_dir)
        result = backend._check_embeddings()
        assert result is False

    @patch("subprocess.run")
    def test_search_bm25_fallback(self, mock_run, kb_dir):
        """Busca usa BM25 quando embeddings indisponíveis."""
        import json

        backend = QmdBackend(kb_dir)
        backend._initialized = True
        backend._has_embeddings = False

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([
            {"path": "doc.md", "title": "Doc", "content": "conteúdo", "score": 0.9}
        ])
        mock_run.return_value = mock_result

        results = backend.search("busca")
        assert len(results) == 1
        assert results[0].title == "Doc"

    @patch("subprocess.run")
    def test_search_falha_retorna_vazio(self, mock_run, kb_dir):
        """Busca que falha retorna lista vazia."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error"
        mock_run.return_value = mock_result

        backend = QmdBackend(kb_dir)
        backend._initialized = True
        backend._has_embeddings = True

        results = backend.search("busca")
        assert results == []

    @patch("subprocess.run")
    def test_reindex_all_com_embeddings(self, mock_run, kb_dir):
        """Reindex com embeddings disponíveis."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        backend = QmdBackend(kb_dir)
        backend._initialized = True
        backend.reindex_all()

        assert backend._has_embeddings is True

    @patch("subprocess.run")
    def test_reindex_all_sem_embeddings(self, mock_run, kb_dir):
        """Reindex quando embeddings falham."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] <= 2:
                # ensure_collection + update ok
                result.returncode = 0
            else:
                # embed falha
                result.returncode = 1
                result.stderr = "error"
            return result

        mock_run.side_effect = side_effect

        backend = QmdBackend(kb_dir)
        backend.reindex_all()

        assert backend._has_embeddings is False


class TestKnowledgeStoreExtended:
    """Testes adicionais para a facade KnowledgeStore."""

    @pytest.fixture
    def kb_dir(self, tmp_path):
        kb = tmp_path / "kb"
        kb.mkdir()
        return kb

    def test_close_sem_fts5(self, kb_dir):
        """Close funciona quando _fts5 é None."""
        store = KnowledgeStore(kb_dir)
        store._fts5 = None
        store.close()  # Não deve lançar exceção

    def test_count_sem_fts5(self, kb_dir):
        """count retorna 0 quando _fts5 é None."""
        store = KnowledgeStore(kb_dir)
        store._fts5 = None
        assert store.count() == 0

    def test_update_score_sem_fts5(self, kb_dir):
        """update_score é no-op quando _fts5 é None."""
        store = KnowledgeStore(kb_dir)
        store._fts5 = None
        store.update_score("doc.md", 1)  # Não deve lançar exceção

    def test_increment_used_sem_fts5(self, kb_dir):
        """increment_used é no-op quando _fts5 é None."""
        store = KnowledgeStore(kb_dir)
        store._fts5 = None
        store.increment_used("doc.md")  # Não deve lançar exceção

    def test_format_for_prompt_com_score(self, kb_dir):
        """format_for_prompt inclui badge de score quando > 0."""
        doc = kb_dir / "popular.md"
        doc.write_text(
            "---\nscore: 10\n---\n# Doc Popular\n\nConteúdo popular.",
            encoding="utf-8",
        )

        store = KnowledgeStore(kb_dir)
        store.reindex_all()
        result = store.format_for_prompt("popular")

        assert "👍" in result
        store.close()

    @patch("shutil.which", return_value="/usr/bin/qmd")
    @patch("subprocess.run")
    def test_init_com_qmd_disponivel(self, mock_run, mock_which, kb_dir):
        """Inicializa com qmd quando disponível."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        store = KnowledgeStore(kb_dir, use_qmd=True)

        assert isinstance(store._backend, QmdBackend)
        assert store._fts5 is not None
        store.close()

    @patch("shutil.which", return_value="/usr/bin/qmd")
    @patch("subprocess.run")
    def test_index_com_qmd_mantém_fts5(self, mock_run, mock_which, kb_dir):
        """Index com qmd também mantém FTS5 atualizado."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        store = KnowledgeStore(kb_dir, use_qmd=True)

        doc = kb_dir / "doc.md"
        doc.write_text("# Doc\n\nTexto.", encoding="utf-8")
        store.index(doc)

        # FTS5 deve ter o documento
        assert store._fts5.count() == 1
        store.close()
