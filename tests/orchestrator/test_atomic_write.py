"""Testes para escrita atômica com permissões seguras."""

import os
import stat

from ai_squad.orchestrator.atomic_write import write_json_atomic, write_text_atomic


def test_write_json_atomic_permissions(tmp_path):
    """Verifica que write_json_atomic cria arquivo com permissão 0o600 (somente dono)."""
    target = tmp_path / "state.json"
    write_json_atomic(target, {"user_id": "123", "secret": "abc"})

    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600, f"Permissão esperada 0o600 (owner-only), obtida {oct(mode)}"


def test_write_text_atomic_permissions(tmp_path):
    """Verifica que write_text_atomic cria arquivo com permissão 0o600."""
    target = tmp_path / "notes.txt"
    write_text_atomic(target, "dados sensíveis")

    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600, f"Permissão esperada 0o600 (owner-only), obtida {oct(mode)}"


def test_write_json_atomic_content(tmp_path):
    """Verifica que o conteúdo JSON é escrito corretamente."""
    target = tmp_path / "data.json"
    data = {"chave": "valor", "lista": [1, 2, 3]}
    write_json_atomic(target, data)

    import json

    with open(target, encoding="utf-8") as f:
        result = json.load(f)
    assert result == data
