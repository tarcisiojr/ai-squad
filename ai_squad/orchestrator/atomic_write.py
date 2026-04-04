"""Escrita atômica compartilhada: temp + fsync + rename.

Garante durabilidade em caso de crash. Usado por state, journal,
conversation e daily_notes.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json_atomic(path: Path, data: dict[str, Any] | list[Any]) -> None:
    """Grava JSON atomicamente: temp + fsync + rename.

    Garante que o arquivo nunca fica corrompido mesmo em caso
    de crash — ou o conteúdo antigo permanece, ou o novo é
    escrito completamente.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2)
    _write_atomic(path, content)


def write_text_atomic(path: Path, text: str) -> None:
    """Grava texto atomicamente: temp + fsync + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(path, text)


def _write_atomic(path: Path, content: str) -> None:
    """Implementação interna de escrita atômica."""
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        suffix=".tmp",
    )
    # Restringe permissões antes de escrever conteúdo sensível
    os.chmod(tmp_path, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
