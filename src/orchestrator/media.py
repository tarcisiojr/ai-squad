"""Detecção e envio de imagens e arquivos Markdown em respostas de agentes."""

import logging
import os
import re
from pathlib import Path

from src.barramento.interface import MessageBus

logger = logging.getLogger("ai-dev-team.media")


async def extract_and_send_media(
    user_id: str, text: str, message_bus: MessageBus,
) -> str:
    """Detecta caminhos de imagem e arquivos .md na resposta e envia via barramento.

    Procura por:
    - Markdown images: ![alt](path)
    - Caminhos absolutos de imagem: /tmp/screenshot.png
    - Markdown links para .md: [titulo](path.md)
    - Caminhos soltos de .md: /workspace/openspec/changes/spec.md
    Retorna texto limpo (sem os caminhos enviados).
    """
    cleaned = text
    sent_files: set[str] = set()

    # 1. Detecta markdown images: ![caption](path)
    md_img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    for match in md_img_pattern.finditer(text):
        caption = match.group(1)
        path = match.group(2)
        if os.path.isfile(path) and path not in sent_files:
            try:
                await message_bus.send_photo(user_id, path, caption)
                sent_files.add(path)
                logger.info("Imagem enviada: %s", path)
            except Exception as e:
                logger.error("Erro ao enviar imagem %s: %s", path, e)
        cleaned = cleaned.replace(match.group(0), "")

    # 2. Detecta caminhos soltos de imagem
    img_pattern = re.compile(
        r'(/[\w/.-]+\.(?:png|jpg|jpeg|gif|webp))', re.IGNORECASE,
    )
    for match in img_pattern.finditer(cleaned):
        path = match.group(1)
        if os.path.isfile(path) and path not in sent_files:
            try:
                await message_bus.send_photo(user_id, path, "")
                sent_files.add(path)
                logger.info("Imagem enviada: %s", path)
            except Exception as e:
                logger.error("Erro ao enviar imagem %s: %s", path, e)
            cleaned = cleaned.replace(path, "")

    # 3. Detecta markdown links para .md: [titulo](path.md)
    md_link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')
    for match in md_link_pattern.finditer(cleaned):
        title = match.group(1)
        path = match.group(2)
        if os.path.isfile(path) and path not in sent_files:
            try:
                content = Path(path).read_text(encoding="utf-8")
                header = f"📄 {title} ({Path(path).name})\n\n"
                max_content = 4096 - len(header) - 50
                if len(content) > max_content:
                    content = content[:max_content] + "\n\n... (truncado)"
                await message_bus.send_message(user_id, f"{header}{content}")
                sent_files.add(path)
                logger.info("Arquivo .md enviado: %s", path)
            except Exception as e:
                logger.error("Erro ao enviar .md %s: %s", path, e)
            cleaned = cleaned.replace(match.group(0), title)

    # 4. Detecta caminhos soltos de .md
    md_path_pattern = re.compile(r'(/[\w/.-]+\.md)\b')
    for match in md_path_pattern.finditer(cleaned):
        path = match.group(1)
        if os.path.isfile(path) and path not in sent_files:
            try:
                content = Path(path).read_text(encoding="utf-8")
                name = Path(path).name
                header = f"📄 {name}\n\n"
                max_content = 4096 - len(header) - 50
                if len(content) > max_content:
                    content = content[:max_content] + "\n\n... (truncado)"
                await message_bus.send_message(user_id, f"{header}{content}")
                sent_files.add(path)
                logger.info("Arquivo .md enviado: %s", path)
            except Exception as e:
                logger.error("Erro ao enviar .md %s: %s", path, e)

    # Limpa linhas vazias duplicadas
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned
