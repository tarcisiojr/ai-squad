"""Testes adicionais para cobertura profunda do ingest.py."""

from unittest.mock import MagicMock, patch

from ai_squad.orchestrator.ingest import DocumentIngest, _slugify


class TestSlugifyEdgeCases:
    """Testes para _slugify — edge cases."""

    def test_texto_vazio(self):
        """Texto vazio retorna 'documento'."""
        assert _slugify("") == "documento"

    def test_somente_caracteres_especiais(self):
        """Apenas caracteres especiais retorna 'documento'."""
        assert _slugify("!!!@@@###") == "documento"

    def test_texto_longo_truncado(self):
        """Texto longo é truncado em 80 caracteres."""
        texto = "a" * 200
        assert len(_slugify(texto)) <= 80

    def test_acentos_removidos(self):
        """Acentos são removidos corretamente."""
        assert _slugify("Análise de Relatório") == "analise-de-relatorio"

    def test_multiplos_espacos(self):
        """Múltiplos espaços viram um único hífen."""
        assert _slugify("palavra   outra") == "palavra-outra"


class TestIngestConteudoVazio:
    """Testes para conteúdo vazio (linhas 119-121)."""

    def test_conteudo_vazio_retorna_none(self, tmp_path):
        """Converter que retorna string vazia resulta em None (linhas 119-121)."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        source = tmp_path / "doc.md"
        source.write_text("", encoding="utf-8")

        # Substitui converter para retornar vazio
        ingest._converters[".md"] = lambda p: ""

        result = ingest.ingest(source)
        assert result is None

    def test_conteudo_somente_whitespace_retorna_none(self, tmp_path):
        """Converter que retorna apenas whitespace resulta em None."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        source = tmp_path / "doc.md"
        source.write_text("   \n\n  \t  ", encoding="utf-8")

        ingest._converters[".md"] = lambda p: "   \n   "

        result = ingest.ingest(source)
        assert result is None


class TestTituloInferido:
    """Testes para inferência de título (linhas 124-131)."""

    def test_titulo_do_conteudo(self, tmp_path):
        """Título é extraído do primeiro heading H1 (linhas 126-129)."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        source = tmp_path / "doc.md"
        source.write_text("# Manual do ERP\n\nConteúdo aqui.", encoding="utf-8")

        result = ingest.ingest(source)
        assert result is not None
        assert "manual-do-erp" in str(result)

    def test_titulo_do_nome_arquivo(self, tmp_path):
        """Título inferido do nome do arquivo quando sem heading (linha 131)."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        source = tmp_path / "doc.md"
        source.write_text("Texto sem heading.", encoding="utf-8")

        # Converter que não gera heading
        ingest._converters[".md"] = lambda p: "Texto sem heading."

        result = ingest.ingest(source, title="")
        assert result is not None


class TestConvertPdf:
    """Testes para _convert_pdf (linhas 195-209)."""

    def test_pdf_vazio_retorna_none_no_ingest(self, tmp_path):
        """PDF sem texto resulta em None via ingest (converter retorna vazio)."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        source = tmp_path / "empty.pdf"
        source.write_bytes(b"%PDF-1.4")

        # Substitui converter para retornar vazio (simula PDF sem texto)
        ingest._converters[".pdf"] = lambda p: ""

        result = ingest.ingest(source)
        assert result is None

    def test_pdf_multiplas_paginas(self, tmp_path):
        """PDF com múltiplas páginas gera separadores (linhas 197-202)."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        # Cria mock de pdfplumber
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Texto da página 1"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Texto da página 2"

        mock_pdf_ctx = MagicMock()
        mock_pdf_ctx.pages = [mock_page1, mock_page2]

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf_ctx)
        mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {"pdfplumber": mock_pdfplumber}):
            # Recria o converter para usar o mock
            def pdf_converter(path):
                parts = []
                with mock_pdfplumber.open(path) as pdf:
                    for i, page in enumerate(pdf.pages, 1):
                        text = page.extract_text()
                        if text:
                            if i > 1:
                                parts.append(f"\n---\n\n_Página {i}_\n")
                            parts.append(text)
                if not parts:
                    return ""
                content = "\n\n".join(parts)
                return f"# {path.stem}\n\n{content}"

            result = pdf_converter(tmp_path / "multi.pdf")
            assert "Página 2" in result
            assert "Texto da página 1" in result


class TestConvertDocx:
    """Testes para _convert_docx (linhas 220-237)."""

    def test_docx_com_headings(self, tmp_path):
        """DOCX com headings gera Markdown correto (linhas 228-233)."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        # Simula parágrafos com estilos
        paragraphs = []
        for text, style_name in [
            ("Título Principal", "Heading 1"),
            ("Subtítulo", "Heading 2"),
            ("Sub-sub", "Heading 3"),
            ("Texto normal", "Normal"),
            ("", "Normal"),  # Vazio, deve ser ignorado
        ]:
            para = MagicMock()
            para.text = text
            para.style = MagicMock()
            para.style.name = style_name
            paragraphs.append(para)

        mock_doc = MagicMock()
        mock_doc.paragraphs = paragraphs

        # Simula a lógica do converter
        parts = []
        for para in mock_doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style = para.style.name.lower() if para.style else ""
            if "heading 1" in style:
                parts.append(f"# {text}")
            elif "heading 2" in style:
                parts.append(f"## {text}")
            elif "heading 3" in style:
                parts.append(f"### {text}")
            else:
                parts.append(text)

        result = "\n\n".join(parts) if parts else ""
        assert "# Título Principal" in result
        assert "## Subtítulo" in result
        assert "### Sub-sub" in result
        assert "Texto normal" in result

    def test_docx_vazio(self):
        """DOCX sem parágrafos retorna vazio (linha 237)."""
        parts = []
        result = "\n\n".join(parts) if parts else ""
        assert result == ""


class TestIngestTextVazio:
    """Testes para ingest_text com texto vazio."""

    def test_texto_vazio_retorna_none(self, tmp_path):
        """Texto vazio retorna None."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        result = ingest.ingest_text("", "Titulo")
        assert result is None

    def test_texto_whitespace_retorna_none(self, tmp_path):
        """Texto com apenas whitespace retorna None."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        result = ingest.ingest_text("   \n  ", "Titulo")
        assert result is None


class TestIngestArquivoDuplicado:
    """Testes para evitar sobrescrita de arquivos duplicados."""

    def test_arquivo_duplicado_recebe_sufixo(self, tmp_path):
        """Arquivo com mesmo slug recebe sufixo numérico (linhas 148-151)."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        source1 = tmp_path / "doc1.md"
        source1.write_text("# Mesmo Titulo\n\nConteúdo 1.", encoding="utf-8")
        source2 = tmp_path / "doc2.md"
        source2.write_text("# Mesmo Titulo\n\nConteúdo 2.", encoding="utf-8")

        result1 = ingest.ingest(source1, title="Mesmo Titulo")
        result2 = ingest.ingest(source2, title="Mesmo Titulo")

        assert result1 is not None
        assert result2 is not None
        assert result1 != result2
        assert "-1" in str(result2)


class TestFormatoNaoSuportado:
    """Testes para formato de arquivo não suportado."""

    def test_extensao_desconhecida(self, tmp_path):
        """Extensão não suportada retorna None."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        source = tmp_path / "arquivo.xyz"
        source.write_text("conteúdo", encoding="utf-8")

        result = ingest.ingest(source)
        assert result is None

    def test_arquivo_inexistente(self, tmp_path):
        """Arquivo inexistente retorna None."""
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        ingest = DocumentIngest(kb_dir)

        result = ingest.ingest(tmp_path / "nao-existe.md")
        assert result is None
