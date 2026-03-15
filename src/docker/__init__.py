"""Arquivos Docker para build da imagem ai-dev-team."""

from pathlib import Path


def get_docker_dir() -> Path:
    """Retorna o diretório contendo o Dockerfile do pacote."""
    return Path(__file__).parent
