"""Pipeline de ingestão de documentos para a knowledge base.

Converte arquivos recebidos (PDF, DOCX, MD, TXT, imagens) para Markdown
estruturado e salva na knowledge base com frontmatter padrão.
"""

import logging
import re
import unicodedata
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml

from ai_squad.orchestrator.atomic_write import write_text_atomic

logger = logging.getLogger("ai-squad.ingest")

# Categorias padrão para documentação
DEFAULT_CATEGORIES = ["sistemas", "processos", "faq"]


def _slugify(text: str) -> str:
    """Gera slug a partir de texto (ex: 'Manual do ERP' → 'manual-do-erp')."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^a-z0-9\s-]", "", ascii_text.lower())
    slug = re.sub(r"[\s]+", "-", clean.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug[:80] or "documento"


def _ensure_frontmatter(content: str, meta: dict[str, Any]) -> str:
    """Adiciona frontmatter se não existir, ou preserva existente."""
    if content.startswith("---\n"):
        return content
    yaml_str = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n{content}"


def _default_frontmatter(source: str, original_filename: str) -> dict[str, Any]:
    """Gera frontmatter padrão para documentos ingeridos."""
    return {
        "score": 0,
        "source": source,
        "original_filename": original_filename,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


class DocumentIngest:
    """Pipeline de conversão de documentos para Markdown.

    Suporta PDF, DOCX, MD, TXT e imagens. Dependências de conversão
    (pdfplumber, python-docx) são opcionais — se não instaladas,
    retorna erro informativo.
    """

    def __init__(self, knowledge_dir: str | Path) -> None:
        self._knowledge_dir = Path(knowledge_dir)
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)

        # Registry de converters por extensão
        self._converters: dict[str, Callable[[Path], str]] = {
            ".pdf": self._convert_pdf,
            ".docx": self._convert_docx,
            ".doc": self._convert_docx,
            ".md": self._convert_markdown,
            ".txt": self._convert_text,
            ".jpg": self._convert_image,
            ".jpeg": self._convert_image,
            ".png": self._convert_image,
        }

    @property
    def supported_extensions(self) -> list[str]:
        """Retorna extensões suportadas."""
        return list(self._converters.keys())

    def ingest(
        self,
        file_path: str | Path,
        category: str = "",
        title: str = "",
    ) -> Path | None:
        """Converte documento para .md e salva na knowledge base.

        Args:
            file_path: Caminho do arquivo fonte.
            category: Subpasta em documentacao/ (sistemas, processos, faq).
            title: Título do documento (inferido do conteúdo se vazio).

        Returns:
            Path do .md gerado, ou None se falhou.
        """
        source = Path(file_path)
        if not source.exists():
            logger.error("Arquivo não encontrado: %s", source)
            return None

        ext = source.suffix.lower()
        converter = self._converters.get(ext)
        if not converter:
            logger.error(
                "Formato não suportado: %s (suportados: %s)", ext, self.supported_extensions
            )
            return None

        # Converte para Markdown
        try:
            content = converter(source)
        except ImportError as e:
            logger.error("Dependência não instalada: %s", e)
            return None
        except Exception as e:
            logger.error("Erro na conversão de %s: %s", source.name, e)
            return None

        if not content or not content.strip():
            logger.warning("Conteúdo vazio após conversão: %s", source.name)
            return None

        # Determina título
        if not title:
            # Tenta extrair do conteúdo
            for line in content.splitlines():
                if line.strip().startswith("# "):
                    title = line.strip()[2:].strip()
                    break
            if not title:
                title = source.stem.replace("-", " ").replace("_", " ").title()

        # Gera frontmatter
        meta = _default_frontmatter(source=ext.lstrip("."), original_filename=source.name)
        content = _ensure_frontmatter(content, meta)

        # Determina destino
        slug = _slugify(title)
        if category:
            dest_dir = self._knowledge_dir / "documentacao" / category
        else:
            dest_dir = self._knowledge_dir / "documentacao"
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / f"{slug}.md"

        # Evita sobrescrever — adiciona sufixo se já existe
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{slug}-{counter}.md"
            counter += 1

        # Salva atomicamente
        write_text_atomic(dest_path, content)
        logger.info("Documento ingerido: %s → %s", source.name, dest_path)
        return dest_path

    def ingest_text(
        self,
        text: str,
        title: str,
        category: str = "atendimentos",
    ) -> Path | None:
        """Salva texto direto como .md na knowledge base (para soluções de atendimento)."""
        if not text or not text.strip():
            return None

        slug = _slugify(title)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"{slug}-{date_str}.md"

        dest_dir = self._knowledge_dir / category
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        meta = _default_frontmatter(source="atendimento", original_filename="")
        content = f"# {title}\n\n{text}"
        content = _ensure_frontmatter(content, meta)

        write_text_atomic(dest_path, content)
        logger.info("Solução registrada: %s", dest_path)
        return dest_path

    # --- Converters ---

    def _convert_pdf(self, path: Path) -> str:
        """Converte PDF para Markdown usando pdfplumber."""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "pdfplumber é necessário para PDF. Instale com: pip install pdfplumber"
            )

        parts: list[str] = []
        pdf = cast(Any, pdfplumber).open(path)
        with pdf:
            for i, page in enumerate(cast(list[Any], pdf.pages), 1):
                text = cast(str, page.extract_text())
                if text:
                    if i > 1:
                        parts.append(f"\n---\n\n_Página {i}_\n")
                    parts.append(text)

        if not parts:
            return ""

        # Tenta estruturar como Markdown básico
        content = "\n\n".join(parts)
        return f"# {path.stem}\n\n{content}"

    def _convert_docx(self, path: Path) -> str:
        """Converte DOCX para Markdown usando python-docx."""
        try:
            import docx as _docx_mod
        except ImportError:
            raise ImportError(
                "python-docx é necessário para DOCX. Instale com: pip install python-docx"
            )

        docx_mod = cast(Any, _docx_mod)
        doc = docx_mod.Document(path)
        parts: list[str] = []
        for para in cast(list[Any], doc.paragraphs):
            text = str(para.text).strip()
            if not text:
                continue

            style: str = str(para.style.name).lower() if para.style else ""
            if "heading 1" in style:
                parts.append(f"# {text}")
            elif "heading 2" in style:
                parts.append(f"## {text}")
            elif "heading 3" in style:
                parts.append(f"### {text}")
            else:
                parts.append(text)

        return "\n\n".join(parts) if parts else ""

    def _convert_markdown(self, path: Path) -> str:
        """Copia Markdown direto (apenas lê)."""
        return path.read_text(encoding="utf-8")

    def _convert_text(self, path: Path) -> str:
        """Converte texto puro para Markdown."""
        text = path.read_text(encoding="utf-8")
        title = path.stem.replace("-", " ").replace("_", " ").title()
        return f"# {title}\n\n{text}"

    def _convert_image(self, path: Path) -> str:
        """Placeholder para imagens — retorna template para descrição via LLM."""
        return (
            f"# Imagem: {path.name}\n\n"
            f"_Imagem recebida. Descrição pendente de análise via LLM._\n\n"
            f"Arquivo original: `{path.name}`\n"
        )
