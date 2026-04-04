"""Sistema de aprendizado entre demandas — SQLite FTS5 para busca."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai-squad.lessons")


class LessonsStore:
    """Persiste licoes aprendidas com busca full-text via SQLite FTS5.

    Cada licao registra o que deu errado, como foi resolvido,
    e o contexto para evitar o mesmo erro no futuro.
    FTS5 permite busca por termos com ranking automatico.
    """

    MAX_LESSONS = 200
    MAX_CONTEXT_LESSONS = 10

    def __init__(self, state_dir: str | Path = "state") -> None:
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._state_dir / "lessons.db"
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Retorna conexao SQLite (lazy, reusa)."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Cria tabelas se nao existirem."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                problem TEXT NOT NULL,
                solution TEXT NOT NULL,
                agent_name TEXT DEFAULT '',
                demand_id TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                used_count INTEGER DEFAULT 0
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(
                problem,
                solution,
                category,
                agent_name,
                content='lessons',
                content_rowid='id',
                tokenize='unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS lessons_ai AFTER INSERT ON lessons BEGIN
                INSERT INTO lessons_fts(rowid, problem, solution, category, agent_name)
                VALUES (new.id, new.problem, new.solution, new.category, new.agent_name);
            END;

            CREATE TRIGGER IF NOT EXISTS lessons_ad AFTER DELETE ON lessons BEGIN
                INSERT INTO lessons_fts(lessons_fts, rowid, problem, solution, category, agent_name)
                VALUES ('delete', old.id, old.problem, old.solution, old.category, old.agent_name);
            END;

            CREATE TRIGGER IF NOT EXISTS lessons_au AFTER UPDATE ON lessons BEGIN
                INSERT INTO lessons_fts(lessons_fts, rowid, problem, solution, category, agent_name)
                VALUES ('delete', old.id, old.problem, old.solution, old.category, old.agent_name);
                INSERT INTO lessons_fts(rowid, problem, solution, category, agent_name)
                VALUES (new.id, new.problem, new.solution, new.category, new.agent_name);
            END;
        """)
        conn.commit()

        # Migra lessons.json se existir (retrocompat)
        self._migrate_from_json()

    def _migrate_from_json(self) -> None:
        """Migra lessons.json para SQLite (executa uma vez)."""
        json_path = self._state_dir / "lessons.json"
        if not json_path.exists():
            return

        try:
            lessons = json.loads(json_path.read_text(encoding="utf-8"))
            if not lessons:
                json_path.unlink()
                return

            conn = self._get_conn()
            # Verifica se ja migrou
            count = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            if count > 0:
                json_path.unlink()
                return

            for lesson in lessons:
                conn.execute(
                    "INSERT INTO lessons (category, problem, solution, agent_name, demand_id, timestamp, used_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        lesson.get("category", ""),
                        lesson.get("problem", ""),
                        lesson.get("solution", ""),
                        lesson.get("agent_name", ""),
                        lesson.get("demand_id", ""),
                        lesson.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        lesson.get("used_count", 0),
                    ),
                )
            conn.commit()
            json_path.rename(json_path.with_suffix(".json.migrated"))
            logger.info("Migradas %d licoes de JSON para SQLite FTS5", len(lessons))
        except Exception as e:
            logger.warning("Erro ao migrar lessons.json: %s", e)

    def add(
        self,
        category: str,
        problem: str,
        solution: str,
        agent_name: str = "",
        demand_id: str = "",
    ) -> None:
        """Registra uma licao aprendida."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO lessons (category, problem, solution, agent_name, demand_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                category,
                problem,
                solution,
                agent_name,
                demand_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()

        # Mantém limite — remove as mais antigas e menos usadas
        count = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
        if count > self.MAX_LESSONS:
            excess = count - self.MAX_LESSONS
            conn.execute(
                "DELETE FROM lessons WHERE id IN ("
                "  SELECT id FROM lessons ORDER BY used_count ASC, timestamp ASC LIMIT ?"
                ")",
                (excess,),
            )
            conn.commit()

        logger.info("Licao registrada: [%s] %s", category, problem[:60])

    def get_relevant(self, context: str = "") -> list[dict[str, Any]]:
        """Retorna licoes relevantes usando FTS5 para busca full-text."""
        conn = self._get_conn()

        if not context or not context.strip():
            # Sem contexto: retorna as mais recentes
            rows = conn.execute(
                "SELECT * FROM lessons ORDER BY timestamp DESC LIMIT ?",
                (self.MAX_CONTEXT_LESSONS,),
            ).fetchall()
            return [dict(r) for r in rows]  # type: ignore[arg-type]

        # Prepara query FTS5: remove caracteres especiais e curtos
        words: list[str] = []
        for word in context.lower().split():
            # Remove pontuacao e palavras muito curtas
            clean = "".join(c for c in word if c.isalnum())
            if len(clean) >= 3:
                words.append(clean)

        if not words:
            rows = conn.execute(
                "SELECT * FROM lessons ORDER BY timestamp DESC LIMIT ?",
                (self.MAX_CONTEXT_LESSONS,),
            ).fetchall()
            return [dict(r) for r in rows]  # type: ignore[arg-type]

        # Busca FTS5 com OR entre termos (encontra qualquer match)
        fts_query = " OR ".join(words[:15])  # Limita termos para performance
        try:
            rows = conn.execute(
                "SELECT l.*, rank FROM lessons l "
                "JOIN lessons_fts ON l.id = lessons_fts.rowid "
                "WHERE lessons_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?",
                (fts_query, self.MAX_CONTEXT_LESSONS),
            ).fetchall()

            if rows:
                return [dict(r) for r in rows]  # type: ignore[arg-type]
        except sqlite3.OperationalError:
            # FTS query invalida — fallback para recentes
            pass

        # Fallback: retorna as mais recentes
        rows = conn.execute(
            "SELECT * FROM lessons ORDER BY timestamp DESC LIMIT ?",
            (self.MAX_CONTEXT_LESSONS,),
        ).fetchall()
        return [dict(r) for r in rows]  # type: ignore[arg-type]

    def format_for_prompt(self, context: str = "") -> str:
        """Formata licoes para injecao no prompt dos agentes."""
        lessons = self.get_relevant(context)
        if not lessons:
            return ""

        partes = ["## Licoes aprendidas (evite repetir erros)\n"]
        for lesson in lessons:
            agent = lesson.get("agent_name", "")
            agent_info = f" ({agent})" if agent else ""
            partes.append(
                f"- **{lesson['category']}**{agent_info}: "
                f"{lesson['problem']} → {lesson['solution']}"
            )

        # Marca como usadas
        conn = self._get_conn()
        for lesson in lessons:
            lid = lesson.get("id")
            if lid:
                conn.execute(
                    "UPDATE lessons SET used_count = used_count + 1 WHERE id = ?",
                    (lid,),
                )
        conn.commit()

        return "\n".join(partes)

    def count(self) -> int:
        """Retorna total de licoes armazenadas."""
        conn = self._get_conn()
        return conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]

    def get_categories(self) -> list[str]:
        """Retorna lista de categorias únicas de lições."""
        conn = self._get_conn()
        rows = conn.execute("SELECT DISTINCT category FROM lessons ORDER BY category").fetchall()
        return [r[0] for r in rows if r[0]]

    def close(self) -> None:
        """Fecha conexao com o banco."""
        if self._conn:
            self._conn.close()
            self._conn = None
