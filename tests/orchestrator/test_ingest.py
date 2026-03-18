"""Testes para DocumentIngest — conversão de documentos para knowledge base."""

import pytest

from src.orchestrator.ingest import DocumentIngest, _slugify
from src.orchestrator.knowledge import parse_frontmatter


class TestSlugify:
    """Testes de geração de slug."""

    def test_texto_simples(self):
        assert _slugify("Manual do ERP") == "manual-do-erp"

    def test_acentos_removidos(self):
        assert _slugify("Configuração de Rede") == "configuracao-de-rede"

    def test_caracteres_especiais(self):
        assert _slugify("FAQ - Perguntas & Respostas!") == "faq-perguntas-respostas"

    def test_texto_vazio(self):
        assert _slugify("") == "documento"

    def test_trunca_em_80_chars(self):
        slug = _slugify("a " * 100)
        assert len(slug) <= 80


class TestDocumentIngest:
    """Testes de ingestão de documentos."""

    @pytest.fixture
    def kb_dir(self, tmp_path):
        """Diretório de knowledge base temporário."""
        kb = tmp_path / "knowledge"
        kb.mkdir()
        return kb

    @pytest.fixture
    def ingest(self, kb_dir):
        """Instância de DocumentIngest."""
        return DocumentIngest(kb_dir)

    def test_ingest_markdown(self, ingest, kb_dir, tmp_path):
        """Verifica ingestão de arquivo Markdown."""
        source = tmp_path / "guia-vpn.md"
        source.write_text("# Guia de VPN\n\nConteúdo do guia.", encoding="utf-8")

        result = ingest.ingest(source, category="sistemas")

        assert result is not None
        assert result.exists()
        assert "documentacao/sistemas" in str(result)
        content = result.read_text(encoding="utf-8")
        assert "Guia de VPN" in content

    def test_ingest_markdown_adiciona_frontmatter(self, ingest, tmp_path):
        """Verifica que frontmatter é adicionado em .md sem frontmatter."""
        source = tmp_path / "doc.md"
        source.write_text("# Título\n\nConteúdo", encoding="utf-8")

        result = ingest.ingest(source)
        content = result.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)
        assert meta["score"] == 0
        assert meta["source"] == "md"

    def test_ingest_markdown_preserva_frontmatter_existente(self, ingest, tmp_path):
        """Verifica que .md com frontmatter existente é preservado."""
        source = tmp_path / "doc.md"
        source.write_text("---\nscore: 5\ntags: [vpn]\n---\n# Título\n", encoding="utf-8")

        result = ingest.ingest(source)
        content = result.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)
        assert meta["score"] == 5
        assert meta["tags"] == ["vpn"]

    def test_ingest_texto_puro(self, ingest, tmp_path):
        """Verifica ingestão de arquivo .txt."""
        source = tmp_path / "notas-reuniao.txt"
        source.write_text("Decisões da reunião:\n1. Migrar para novo CRM\n2. Prazo: 30 dias", encoding="utf-8")

        result = ingest.ingest(source, category="processos", title="Notas da Reunião")

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "Notas da Reunião" in content or "notas" in str(result).lower()

    def test_ingest_imagem_gera_placeholder(self, ingest, tmp_path):
        """Verifica que imagem gera placeholder para descrição via LLM."""
        source = tmp_path / "erro-tela.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\n")  # Header PNG mínimo

        result = ingest.ingest(source)

        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "Imagem" in content
        assert "LLM" in content

    def test_ingest_arquivo_inexistente(self, ingest):
        """Verifica que arquivo inexistente retorna None."""
        result = ingest.ingest("/caminho/inexistente/doc.pdf")
        assert result is None

    def test_ingest_formato_nao_suportado(self, ingest, tmp_path):
        """Verifica que formato não suportado retorna None."""
        source = tmp_path / "arquivo.xyz"
        source.write_text("conteúdo", encoding="utf-8")
        result = ingest.ingest(source)
        assert result is None

    def test_ingest_nao_sobrescreve_existente(self, ingest, tmp_path):
        """Verifica que arquivo com mesmo nome gera sufixo numérico."""
        source = tmp_path / "doc.md"
        source.write_text("# Título\n\nConteúdo 1", encoding="utf-8")
        result1 = ingest.ingest(source, title="Mesmo Título")

        source.write_text("# Título\n\nConteúdo 2", encoding="utf-8")
        result2 = ingest.ingest(source, title="Mesmo Título")

        assert result1 != result2
        assert result1.exists()
        assert result2.exists()

    def test_ingest_titulo_inferido_do_conteudo(self, ingest, tmp_path):
        """Verifica que título é extraído do heading do documento."""
        source = tmp_path / "arquivo.md"
        source.write_text("# Meu Título Especial\n\nConteúdo", encoding="utf-8")

        result = ingest.ingest(source)
        assert "meu-titulo-especial" in str(result)

    def test_ingest_titulo_inferido_do_filename(self, ingest, tmp_path):
        """Verifica que título é inferido do nome do arquivo quando não há heading."""
        source = tmp_path / "guia-rapido.txt"
        source.write_text("Conteúdo sem heading", encoding="utf-8")

        result = ingest.ingest(source)
        assert "guia-rapido" in str(result).lower()

    def test_ingest_text_cria_atendimento(self, ingest, kb_dir):
        """Verifica que ingest_text salva na categoria correta."""
        result = ingest.ingest_text(
            text="## Problema\nVPN não conecta\n\n## Solução\nReiniciar FortiClient",
            title="VPN não conecta",
            category="atendimentos",
        )

        assert result is not None
        assert "atendimentos" in str(result)
        content = result.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)
        assert meta["source"] == "atendimento"
        assert meta["score"] == 0

    def test_ingest_text_vazio_retorna_none(self, ingest):
        """Verifica que texto vazio retorna None."""
        assert ingest.ingest_text("", "título") is None
        assert ingest.ingest_text("   ", "título") is None

    def test_supported_extensions(self, ingest):
        """Verifica que extensões suportadas são listadas."""
        exts = ingest.supported_extensions
        assert ".pdf" in exts
        assert ".md" in exts
        assert ".txt" in exts
        assert ".jpg" in exts
        assert ".docx" in exts
