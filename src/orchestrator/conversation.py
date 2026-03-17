"""Persistência de histórico de conversa por demanda com sumarização."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

logger = logging.getLogger("ai-dev-team.conversation")


class ConversationStore:
    """Salva e carrega histórico de conversa agente ↔ usuário.

    Cada demanda tem seu próprio arquivo conversation.json
    com escrita atômica (temp + fsync + rename) para evitar corrupção.

    Suporta sumarização automática: quando o histórico excede
    SUMMARIZE_THRESHOLD mensagens, as mais antigas são condensadas
    em um resumo via LLM, mantendo apenas as últimas N mensagens.
    """

    MAX_CONTEXT_MESSAGES = 20
    SUMMARIZE_THRESHOLD = 20
    KEEP_RECENT = 10

    def __init__(self, state_dir: str = "state") -> None:
        self._state_dir = Path(state_dir)
        # Callback para sumarização via LLM (registrado pelo engine)
        self._summarize_fn: Callable[[str], str] | None = None

    def set_summarize_callback(self, callback: Callable[[str], str]) -> None:
        """Registra callback async para sumarizar texto via LLM.

        O callback recebe o texto a sumarizar e retorna o resumo.
        Assinatura: async def summarize(text: str) -> str
        """
        self._summarize_fn = callback

    def _conversation_path(self, demand_id: str) -> Path:
        """Retorna caminho do arquivo de conversa."""
        demand_dir = self._state_dir / demand_id
        demand_dir.mkdir(parents=True, exist_ok=True)
        return demand_dir / "conversation.json"

    def _summary_path(self, demand_id: str) -> Path:
        """Retorna caminho do arquivo de resumo acumulado."""
        demand_dir = self._state_dir / demand_id
        demand_dir.mkdir(parents=True, exist_ok=True)
        return demand_dir / "conversation_summary.txt"

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

    def load_summary(self, demand_id: str) -> str:
        """Carrega resumo acumulado da demanda."""
        path = self._summary_path(demand_id)
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _save_summary(self, demand_id: str, summary: str) -> None:
        """Salva resumo acumulado com escrita atômica."""
        path = self._summary_path(demand_id)
        self._write_atomic_text(path, summary)

    async def summarize_if_needed(self, demand_id: str) -> bool:
        """Sumariza histórico se exceder threshold.

        Quando o número de mensagens > SUMMARIZE_THRESHOLD:
        1. Separa mensagens antigas (tudo exceto as últimas KEEP_RECENT)
        2. Gera resumo das antigas via LLM
        3. Acumula com resumo anterior (se houver)
        4. Mantém apenas as mensagens recentes no arquivo

        Retorna True se sumarização foi realizada.
        """
        if not self._summarize_fn:
            return False

        messages = self.load(demand_id)
        if len(messages) <= self.SUMMARIZE_THRESHOLD:
            return False

        # Separa mensagens antigas das recentes
        antigas = messages[:-self.KEEP_RECENT]
        recentes = messages[-self.KEEP_RECENT:]

        # Formata mensagens antigas para sumarização
        texto_antigas = self._format_messages_for_summary(antigas)

        # Acumula com resumo anterior
        resumo_anterior = self.load_summary(demand_id)
        if resumo_anterior:
            texto_para_sumarizar = (
                f"Resumo anterior da conversa:\n{resumo_anterior}\n\n"
                f"Novas mensagens para incorporar ao resumo:\n{texto_antigas}"
            )
        else:
            texto_para_sumarizar = texto_antigas

        prompt = (
            "Resuma a conversa abaixo de forma concisa, preservando:\n"
            "- Decisoes tomadas e seus motivos\n"
            "- Tarefas delegadas e status\n"
            "- Problemas encontrados e solucoes\n"
            "- Contexto importante para continuidade\n\n"
            f"{texto_para_sumarizar}"
        )

        try:
            novo_resumo = await self._summarize_fn(prompt)
            if novo_resumo and len(novo_resumo.strip()) > 10:
                self._save_summary(demand_id, novo_resumo.strip())

                # Substitui mensagens pelo conjunto reduzido
                path = self._conversation_path(demand_id)
                self._write_atomic(path, recentes)

                logger.info(
                    "Sumarizacao: %d mensagens → resumo + %d recentes (demand: %s)",
                    len(antigas), len(recentes), demand_id,
                )
                return True
        except Exception as e:
            logger.warning("Falha na sumarizacao: %s", e)

        return False

    def _format_messages_for_summary(self, messages: list[dict]) -> str:
        """Formata lista de mensagens como texto para sumarização."""
        partes = []
        for msg in messages:
            role_label = msg.get("agent_name") or msg.get("role", "?")
            content = msg.get("content", "")
            # Trunca mensagens muito longas para economizar tokens
            if len(content) > 500:
                content = content[:500] + "..."
            partes.append(f"[{role_label}]: {content}")
        return "\n".join(partes)

    def get_context_messages(self, demand_id: str) -> list[dict]:
        """Retorna mensagens para injeção no contexto, com resumo se disponível."""
        messages = self.load(demand_id)

        # Se há resumo acumulado, injeta como primeira mensagem
        summary = self.load_summary(demand_id)
        prefix: list[dict] = []
        if summary:
            prefix.append({
                "role": "system",
                "content": f"[Resumo das mensagens anteriores]\n{summary}",
                "agent_name": "",
                "timestamp": "",
            })

        if len(messages) <= self.MAX_CONTEXT_MESSAGES:
            return prefix + messages

        # Sem resumo: indica mensagens omitidas
        if not summary:
            omitidas = len(messages) - self.MAX_CONTEXT_MESSAGES
            prefix.append({
                "role": "system",
                "content": f"[{omitidas} mensagens anteriores omitidas]",
                "agent_name": "",
                "timestamp": "",
            })

        recentes = messages[-self.MAX_CONTEXT_MESSAGES:]
        return prefix + recentes

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

    def message_count(self, demand_id: str) -> int:
        """Retorna total de mensagens no histórico."""
        return len(self.load(demand_id))

    def _write_atomic(self, path: Path, data: list[dict]) -> None:
        """Escrita atômica: temp + fsync + rename."""
        content = json.dumps(data, ensure_ascii=False, indent=2)

        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            suffix=".tmp",
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            Path(tmp_path).replace(path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def _write_atomic_text(self, path: Path, text: str) -> None:
        """Escrita atômica de texto plano: temp + fsync + rename."""
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            suffix=".tmp",
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            Path(tmp_path).replace(path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
