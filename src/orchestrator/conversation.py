"""Persistência de histórico de conversa por demanda."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class ConversationStore:
    """Salva e carrega histórico de conversa agente ↔ usuário.

    Cada demanda tem seu próprio arquivo conversation.json
    com escrita atômica (temp + rename) para evitar corrupção.
    """

    MAX_CONTEXT_MESSAGES = 20

    def __init__(self, state_dir: str = "state") -> None:
        self._state_dir = Path(state_dir)

    def _conversation_path(self, demand_id: str) -> Path:
        """Retorna caminho do arquivo de conversa."""
        demand_dir = self._state_dir / demand_id
        demand_dir.mkdir(parents=True, exist_ok=True)
        return demand_dir / "conversation.json"

    def save_message(
        self,
        demand_id: str,
        role: str,
        content: str,
        agent_name: str = "",
    ) -> None:
        """Salva uma mensagem no histórico da demanda."""
        path = self._conversation_path(demand_id)

        messages = self.load(demand_id)
        messages.append({
            "role": role,
            "agent_name": agent_name,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._write_atomic(path, messages)

    def load(self, demand_id: str) -> list[dict]:
        """Carrega histórico de conversa da demanda."""
        path = self._conversation_path(demand_id)
        if not path.exists():
            return []

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def get_context_messages(self, demand_id: str) -> list[dict]:
        """Retorna mensagens para injeção no contexto, com limite."""
        messages = self.load(demand_id)

        if len(messages) <= self.MAX_CONTEXT_MESSAGES:
            return messages

        # Resumo das mensagens antigas + últimas N
        resumo = f"[{len(messages) - self.MAX_CONTEXT_MESSAGES} mensagens anteriores omitidas]"
        recentes = messages[-self.MAX_CONTEXT_MESSAGES:]

        return [{"role": "system", "content": resumo, "agent_name": "", "timestamp": ""}] + recentes

    def format_history_for_prompt(self, demand_id: str) -> str:
        """Formata histórico como texto para incluir no prompt."""
        messages = self.get_context_messages(demand_id)
        if not messages:
            return ""

        partes = ["## Histórico da conversa\n"]
        for msg in messages:
            role_label = msg.get("agent_name", msg["role"]) or msg["role"]
            partes.append(f"**{role_label}**: {msg['content']}\n")

        return "\n".join(partes)

    def _write_atomic(self, path: Path, data: list[dict]) -> None:
        """Escrita atômica: temp + rename."""
        content = json.dumps(data, ensure_ascii=False, indent=2)

        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            suffix=".tmp",
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp_path).replace(path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
