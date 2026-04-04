"""Testes para detecção e envio de imagens e arquivos Markdown."""

import pytest
from unittest.mock import AsyncMock, PropertyMock, MagicMock
from pathlib import Path

from ai_squad.orchestrator.media import extract_and_send_media


def _mock_bus() -> AsyncMock:
    """Cria mock de MessageBus."""
    bus = AsyncMock()
    return bus


class TestExtractAndSendMediaNoImages:
    """Verifica comportamento quando não há imagens no texto."""

    @pytest.mark.asyncio
    async def test_texto_simples_sem_imagens(self):
        """Texto sem imagens retorna o mesmo texto limpo."""
        bus = _mock_bus()
        result = await extract_and_send_media("user1", "Apenas texto normal.", bus)
        assert result == "Apenas texto normal."
        bus.send_photo.assert_not_called()
        bus.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_texto_vazio(self):
        """Texto vazio retorna string vazia."""
        bus = _mock_bus()
        result = await extract_and_send_media("user1", "", bus)
        assert result == ""

    @pytest.mark.asyncio
    async def test_texto_com_codigo_markdown(self):
        """Texto com código Markdown (sem imagens) não é alterado."""
        bus = _mock_bus()
        text = "```python\nprint('hello')\n```"
        result = await extract_and_send_media("user1", text, bus)
        assert "print('hello')" in result


class TestExtractMarkdownImages:
    """Verifica detecção de imagens Markdown ![alt](path)."""

    @pytest.mark.asyncio
    async def test_imagem_markdown_existente(self, tmp_path):
        """Imagem Markdown com arquivo existente é enviada."""
        img = tmp_path / "screenshot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")

        bus = _mock_bus()
        text = f"Veja a imagem: ![Screenshot]({img})"
        result = await extract_and_send_media("user1", text, bus)

        bus.send_photo.assert_called_once_with("user1", str(img), "Screenshot")
        assert str(img) not in result
        assert "Screenshot" not in result

    @pytest.mark.asyncio
    async def test_imagem_markdown_inexistente(self):
        """Imagem Markdown com arquivo inexistente não é enviada."""
        bus = _mock_bus()
        text = "Veja: ![img](/caminho/inexistente/foto.png)"
        result = await extract_and_send_media("user1", text, bus)

        bus.send_photo.assert_not_called()
        # O padrão Markdown é removido mesmo sem envio
        assert "![img]" not in result

    @pytest.mark.asyncio
    async def test_multiplas_imagens_markdown(self, tmp_path):
        """Múltiplas imagens Markdown são todas enviadas."""
        img1 = tmp_path / "a.png"
        img2 = tmp_path / "b.jpg"
        img1.write_bytes(b"\x89PNG")
        img2.write_bytes(b"\xff\xd8")

        bus = _mock_bus()
        text = f"![A]({img1})\nTexto\n![B]({img2})"
        result = await extract_and_send_media("user1", text, bus)

        assert bus.send_photo.call_count == 2
        assert "Texto" in result

    @pytest.mark.asyncio
    async def test_imagem_markdown_erro_envio(self, tmp_path):
        """Erro ao enviar imagem não impede processamento do resto."""
        img = tmp_path / "erro.png"
        img.write_bytes(b"\x89PNG")

        bus = _mock_bus()
        bus.send_photo.side_effect = RuntimeError("Falha no envio")
        text = f"Antes ![img]({img}) Depois"
        result = await extract_and_send_media("user1", text, bus)

        # Texto ainda é limpo
        assert "Depois" in result


class TestExtractLooseImagePaths:
    """Verifica detecção de caminhos soltos de imagem."""

    @pytest.mark.asyncio
    async def test_caminho_solto_existente(self, tmp_path):
        """Caminho absoluto de imagem existente é enviado."""
        img = tmp_path / "chart.png"
        img.write_bytes(b"\x89PNG")

        bus = _mock_bus()
        text = f"Resultado em {img}"
        result = await extract_and_send_media("user1", text, bus)

        bus.send_photo.assert_called_once_with("user1", str(img), "")
        assert str(img) not in result

    @pytest.mark.asyncio
    async def test_caminho_solto_inexistente(self):
        """Caminho absoluto de imagem inexistente é ignorado."""
        bus = _mock_bus()
        text = "Veja /tmp/nao-existe-xyz.png"
        result = await extract_and_send_media("user1", text, bus)

        bus.send_photo.assert_not_called()


class TestExtractMarkdownLinks:
    """Verifica detecção de links para arquivos .md."""

    @pytest.mark.asyncio
    async def test_link_md_existente(self, tmp_path):
        """Link Markdown para .md existente é enviado como texto."""
        md_file = tmp_path / "spec.md"
        md_file.write_text("# Spec\n\nConteúdo da spec.", encoding="utf-8")

        bus = _mock_bus()
        text = f"Veja [Especificação]({md_file})"
        result = await extract_and_send_media("user1", text, bus)

        bus.send_message.assert_called_once()
        msg = bus.send_message.call_args[0][1]
        assert "Especificação" in msg
        assert "Conteúdo da spec" in msg
        # Link substituído pelo título
        assert "Especificação" in result

    @pytest.mark.asyncio
    async def test_link_md_inexistente(self):
        """Link para .md inexistente é ignorado."""
        bus = _mock_bus()
        text = "Veja [Doc](/nao/existe.md)"
        result = await extract_and_send_media("user1", text, bus)

        bus.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_link_md_truncado(self, tmp_path):
        """Arquivo .md grande é truncado."""
        md_file = tmp_path / "grande.md"
        # Conteúdo maior que 4096 chars
        md_file.write_text("# Grande\n\n" + "x" * 5000, encoding="utf-8")

        bus = _mock_bus()
        text = f"Veja [Doc Grande]({md_file})"
        await extract_and_send_media("user1", text, bus)

        bus.send_message.assert_called_once()
        msg = bus.send_message.call_args[0][1]
        assert "truncado" in msg


class TestExtractLooseMdPaths:
    """Verifica detecção de caminhos soltos de .md."""

    @pytest.mark.asyncio
    async def test_caminho_solto_md_existente(self, tmp_path):
        """Caminho absoluto de .md existente é enviado."""
        md_file = tmp_path / "notas.md"
        md_file.write_text("# Notas\n\nConteúdo.", encoding="utf-8")

        bus = _mock_bus()
        text = f"Arquivo gerado: {md_file}"
        result = await extract_and_send_media("user1", text, bus)

        bus.send_message.assert_called_once()
        msg = bus.send_message.call_args[0][1]
        assert "notas.md" in msg

    @pytest.mark.asyncio
    async def test_caminho_solto_md_inexistente(self):
        """Caminho absoluto de .md inexistente é ignorado."""
        bus = _mock_bus()
        text = "Resultado: /tmp/nao-existe-xyz.md"
        result = await extract_and_send_media("user1", text, bus)

        bus.send_message.assert_not_called()


class TestResolveRelativePath:
    """Verifica resolução de caminhos relativos."""

    @pytest.mark.asyncio
    async def test_caminho_relativo_markdown_image(self, tmp_path):
        """Caminho relativo na imagem Markdown é resolvido pelo workspace."""
        img = tmp_path / "docs" / "img.png"
        img.parent.mkdir(parents=True)
        img.write_bytes(b"\x89PNG")

        bus = _mock_bus()
        text = "![img](docs/img.png)"
        result = await extract_and_send_media(
            "user1", text, bus, workspace=str(tmp_path)
        )

        bus.send_photo.assert_called_once()


class TestCleanup:
    """Verifica limpeza de linhas vazias duplicadas."""

    @pytest.mark.asyncio
    async def test_linhas_vazias_duplicadas_removidas(self):
        """Múltiplas linhas vazias são condensadas."""
        bus = _mock_bus()
        text = "Linha 1\n\n\n\n\nLinha 2"
        result = await extract_and_send_media("user1", text, bus)
        assert result == "Linha 1\n\nLinha 2"


class TestDuplicateImages:
    """Verifica que imagens duplicadas não são enviadas duas vezes."""

    @pytest.mark.asyncio
    async def test_mesma_imagem_nao_envia_duplicado(self, tmp_path):
        """Mesma imagem referenciada duas vezes só é enviada uma vez."""
        img = tmp_path / "unica.png"
        img.write_bytes(b"\x89PNG")

        bus = _mock_bus()
        text = f"![A]({img})\n![B]({img})"
        await extract_and_send_media("user1", text, bus)

        # Primeira chamada envia, segunda pula (sent_files)
        assert bus.send_photo.call_count == 1
