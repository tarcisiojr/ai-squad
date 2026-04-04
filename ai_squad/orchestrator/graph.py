"""Grafo de conhecimento relacional — SQLite com extração via LLM.

Conecta entidades e relações extraídas de demandas, lições e resultados
de agentes. Usa recursive CTEs para traversal e FTS5 para busca.
Reforço automático de peso em relações vistas repetidamente.
"""

import asyncio
import json
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger("ai-squad.graph")

# Tipos permitidos para entidades e relações
ENTITY_TYPES = frozenset(
    {
        "bug",
        "pattern",
        "module",
        "technology",
        "decision",
        "agent",
        "concept",
        "artifact",
        "quality",
    }
)
RELATION_TYPES = frozenset(
    {
        "caused_by",
        "resolved_by",
        "affects",
        "uses",
        "produced",
        "depends_on",
        "related_to",
        "rejected_by",
        "improved_by",
    }
)

# Prompt para extração de entidades e relações via LLM
_EXTRACTION_PROMPT = """\
Analise o texto e extraia entidades e relações. Retorne APENAS JSON valido:

{{
  "entities": [
    {{"name": "nome-normalizado", "type": "tipo", "description": "descricao curta"}}
  ],
  "relations": [
    {{"from": "entidade_origem", "to": "entidade_destino", "type": "tipo_relacao", "evidence": "trecho que justifica"}}
  ]
}}

Tipos de entidade: {entity_types}
Tipos de relacao: {relation_types}

Regras:
- Normalize nomes: lowercase, sem acentos, use hifen para separar palavras
- Seja especifico: "auth-middleware" e melhor que "modulo"
- Prefira reutilizar entidades existentes (lista abaixo)
- So crie relacoes com evidencia no texto
- Minimo de entidades/relacoes uteis, sem ruido

Entidades existentes no grafo (reutilize quando possivel):
{existing_entities}

Texto para analisar:
{text}"""


@dataclass
class GraphEntity:
    """Entidade do grafo."""

    name: str
    type: str
    description: str = ""
    mention_count: int = 1
    demand_id: str = ""


@dataclass
class GraphRelation:
    """Relação entre entidades."""

    from_name: str
    from_type: str
    to_name: str
    to_type: str
    rel_type: str
    weight: int = 1
    evidence: str = ""
    demand_id: str = ""


@dataclass
class TraversalResult:
    """Resultado de traversal no grafo."""

    entities: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    relations: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())


class GraphStore:
    """Grafo de conhecimento em SQLite com extração via LLM.

    Segue o mesmo padrão do LessonsStore: lazy connection, FTS5,
    limites configuráveis e formatação para prompt.
    """

    MAX_ENTITIES = 500
    MAX_RELATIONS = 2000
    MAX_TRAVERSAL_DEPTH = 3
    MAX_CONTEXT_RESULTS = 8
    # Idade máxima (dias) para entidades com mention_count=1
    PRUNE_AGE_DAYS = 30
    # Intervalo mínimo (segundos) entre ingestões da mesma demanda
    THROTTLE_SECONDS = 10

    def __init__(self, state_dir: str | Path = "state") -> None:
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._state_dir / "graph.db"
        self._conn: sqlite3.Connection | None = None
        self._extract_fn: Callable[..., Any] | None = None
        # Controle de throttle: demand_id → timestamp da última ingestão
        self._last_ingest: dict[str, float] = {}
        self._init_db()

    def set_extract_callback(self, callback: Callable[..., Any]) -> None:
        """Registra callback async para extrair entidades via LLM.

        Assinatura: async def extract(prompt: str) -> str
        """
        self._extract_fn = callback

    def _get_conn(self) -> sqlite3.Connection:
        """Retorna conexão SQLite (lazy, reusa)."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Cria tabelas se não existirem."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT DEFAULT '',
                mention_count INTEGER DEFAULT 1,
                demand_id TEXT DEFAULT '',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                UNIQUE(name, type)
            );

            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                to_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                rel_type TEXT NOT NULL,
                weight INTEGER DEFAULT 1,
                evidence TEXT DEFAULT '',
                demand_id TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                UNIQUE(from_id, to_id, rel_type)
            );

            CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_id);
            CREATE INDEX IF NOT EXISTS idx_relations_to ON relations(to_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
                name,
                description,
                content='entities',
                content_rowid='id',
                tokenize='unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
                INSERT INTO entities_fts(rowid, name, description)
                VALUES (new.id, new.name, new.description);
            END;

            CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
                INSERT INTO entities_fts(entities_fts, rowid, name, description)
                VALUES ('delete', old.id, old.name, old.description);
            END;

            CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
                INSERT INTO entities_fts(entities_fts, rowid, name, description)
                VALUES ('delete', old.id, old.name, old.description);
                INSERT INTO entities_fts(rowid, name, description)
                VALUES (new.id, new.name, new.description);
            END;

            PRAGMA foreign_keys = ON;
        """)
        conn.commit()

    # --- Escrita ---

    def add_entity(
        self,
        name: str,
        entity_type: str,
        description: str = "",
        demand_id: str = "",
    ) -> int | None:
        """Adiciona ou atualiza entidade. Retorna ID."""
        name_norm = self._normalize_name(name)
        if not name_norm or entity_type not in ENTITY_TYPES:
            return None

        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()

        existing = conn.execute(
            "SELECT id, mention_count FROM entities WHERE name = ? AND type = ?",
            (name_norm, entity_type),
        ).fetchone()

        if existing:
            # Atualiza: incrementa mention_count e last_seen
            new_desc = description if description else None
            if new_desc:
                conn.execute(
                    "UPDATE entities SET mention_count = mention_count + 1, "
                    "last_seen = ?, description = ? WHERE id = ?",
                    (now, new_desc, existing["id"]),
                )
            else:
                conn.execute(
                    "UPDATE entities SET mention_count = mention_count + 1, "
                    "last_seen = ? WHERE id = ?",
                    (now, existing["id"]),
                )
            conn.commit()
            return existing["id"]

        conn.execute(
            "INSERT INTO entities (name, type, description, demand_id, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name_norm, entity_type, description, demand_id, now, now),
        )
        conn.commit()
        entity_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        self._prune_if_needed()
        return entity_id

    def add_relation(
        self,
        from_name: str,
        from_type: str,
        to_name: str,
        to_type: str,
        rel_type: str,
        evidence: str = "",
        demand_id: str = "",
    ) -> bool:
        """Adiciona ou reforça relação entre entidades. Retorna True se sucesso."""
        if rel_type not in RELATION_TYPES:
            return False

        from_name = self._normalize_name(from_name)
        to_name = self._normalize_name(to_name)
        if not from_name or not to_name:
            return False

        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()

        # Busca IDs das entidades (devem existir)
        from_row = conn.execute(
            "SELECT id FROM entities WHERE name = ? AND type = ?",
            (from_name, from_type),
        ).fetchone()
        to_row = conn.execute(
            "SELECT id FROM entities WHERE name = ? AND type = ?",
            (to_name, to_type),
        ).fetchone()

        if not from_row or not to_row:
            return False

        from_id = from_row["id"]
        to_id = to_row["id"]

        # Verifica se relação já existe → reforça peso
        existing = conn.execute(
            "SELECT id, weight FROM relations WHERE from_id = ? AND to_id = ? AND rel_type = ?",
            (from_id, to_id, rel_type),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE relations SET weight = weight + 1, timestamp = ? WHERE id = ?",
                (now, existing["id"]),
            )
            conn.commit()
            return True

        conn.execute(
            "INSERT INTO relations (from_id, to_id, rel_type, evidence, demand_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (from_id, to_id, rel_type, evidence, demand_id, now),
        )
        conn.commit()

        self._prune_if_needed()
        return True

    def reinforce(self, from_name: str, to_name: str, delta: int = 1) -> bool:
        """Ajusta peso de uma relação (qualquer tipo entre as entidades)."""
        from_name = self._normalize_name(from_name)
        to_name = self._normalize_name(to_name)
        if not from_name or not to_name:
            return False

        conn = self._get_conn()
        result = conn.execute(
            "UPDATE relations SET weight = weight + ? "
            "WHERE from_id IN (SELECT id FROM entities WHERE name = ?) "
            "AND to_id IN (SELECT id FROM entities WHERE name = ?)",
            (delta, from_name, to_name),
        )
        conn.commit()
        return result.rowcount > 0

    # --- Leitura ---

    def traverse(self, entity_name: str, depth: int = 3) -> TraversalResult:
        """Navega relações a partir de uma entidade via recursive CTE."""
        entity_name = self._normalize_name(entity_name)
        if not entity_name:
            return TraversalResult()

        depth = min(depth, self.MAX_TRAVERSAL_DEPTH)
        conn = self._get_conn()

        # Encontra entidade raiz
        root = conn.execute("SELECT id FROM entities WHERE name = ?", (entity_name,)).fetchone()
        if not root:
            return TraversalResult()

        root_id = root["id"]

        # Recursive CTE: navega relações em ambas as direções
        rows = conn.execute(
            """
            WITH RECURSIVE graph_walk(entity_id, depth) AS (
                SELECT ?, 0
                UNION ALL
                SELECT
                    CASE
                        WHEN r.from_id = gw.entity_id THEN r.to_id
                        ELSE r.from_id
                    END,
                    gw.depth + 1
                FROM graph_walk gw
                JOIN relations r ON r.from_id = gw.entity_id OR r.to_id = gw.entity_id
                WHERE gw.depth < ?
            )
            SELECT DISTINCT e.* FROM entities e
            JOIN graph_walk gw ON e.id = gw.entity_id
            ORDER BY e.mention_count DESC
            LIMIT 50
            """,
            (root_id, depth),
        ).fetchall()

        entity_ids: set[Any] = {row["id"] for row in rows}
        entities: list[dict[str, Any]] = [dict(row) for row in rows]  # type: ignore[arg-type]

        # Busca relações entre as entidades encontradas
        relations: list[dict[str, Any]] = []
        if entity_ids:
            placeholders = ",".join("?" * len(entity_ids))
            rel_rows = conn.execute(
                f"SELECT r.*, ef.name as from_name, ef.type as from_type, "
                f"et.name as to_name, et.type as to_type "
                f"FROM relations r "
                f"JOIN entities ef ON ef.id = r.from_id "
                f"JOIN entities et ON et.id = r.to_id "
                f"WHERE r.from_id IN ({placeholders}) AND r.to_id IN ({placeholders}) "
                f"ORDER BY r.weight DESC",
                list(entity_ids) + list(entity_ids),
            ).fetchall()
            relations = [dict(row) for row in rel_rows]  # type: ignore[arg-type]

        return TraversalResult(entities=entities, relations=relations)

    def query(self, text: str, limit: int = 10) -> TraversalResult:
        """Busca entidades via FTS5 e expande com traversal."""
        if not text or not text.strip():
            return TraversalResult()

        conn = self._get_conn()

        # Prepara query FTS5
        words: list[str] = []
        for word in text.lower().split():
            clean = "".join(c for c in word if c.isalnum() or c == "-")
            if len(clean) >= 3:
                # FTS5 trata hífen como separador — usa aspas para termos compostos
                if "-" in clean:
                    words.append(f'"{clean}"')
                else:
                    words.append(clean)

        if not words:
            return TraversalResult()

        fts_query = " OR ".join(words[:15])

        try:
            rows = conn.execute(
                "SELECT e.* FROM entities e "
                "JOIN entities_fts ON e.id = entities_fts.rowid "
                "WHERE entities_fts MATCH ? "
                "ORDER BY e.mention_count DESC "
                "LIMIT ?",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            logger.warning("Query FTS5 invalida: %s", fts_query)
            return TraversalResult()

        if not rows:
            return TraversalResult()

        # Expande cada entidade com traversal depth=2
        all_entities: dict[int, dict[str, Any]] = {}
        all_relations: list[dict[str, Any]] = []

        for row in rows:
            result = self.traverse(row["name"], depth=2)
            for ent in result.entities:
                all_entities[ent["id"]] = ent
            all_relations.extend(result.relations)

        # Deduplica relações
        seen_rels: set[tuple[Any, ...]] = set()
        unique_relations: list[dict[str, Any]] = []
        for rel in all_relations:
            key = (rel["from_id"], rel["to_id"], rel["rel_type"])
            if key not in seen_rels:
                seen_rels.add(key)
                unique_relations.append(rel)

        entities = sorted(all_entities.values(), key=lambda e: e["mention_count"], reverse=True)
        return TraversalResult(entities=entities[:limit], relations=unique_relations)

    def format_for_prompt(self, query_text: str) -> str:
        """Busca e formata resultado para injeção no prompt."""
        result = self.query(query_text, limit=self.MAX_CONTEXT_RESULTS)
        if not result.entities:
            return ""

        # Agrupa relações por entidade de origem
        rel_by_entity: dict[str, list[dict[str, Any]]] = {}
        for rel in result.relations:
            from_name = rel.get("from_name", "")
            rel_by_entity.setdefault(from_name, []).append(rel)

        parts = ["## Conhecimento relacionado (grafo)\n"]
        for ent in result.entities[: self.MAX_CONTEXT_RESULTS]:
            name = ent["name"]
            etype = ent["type"]
            count = ent["mention_count"]
            desc = ent.get("description", "")

            badge = f" (mencoes: {count})" if count > 1 else ""
            parts.append(f"**{name}** ({etype}){badge}")
            if desc:
                parts.append(f"  {desc}")

            rels = rel_by_entity.get(name, [])
            for rel in rels[:5]:
                to_name = rel.get("to_name", "?")
                rel_type = rel["rel_type"].replace("_", " ")
                weight = rel.get("weight", 1)
                weight_info = f" [peso: {weight}]" if weight > 1 else ""
                parts.append(f"  → {rel_type}: {to_name}{weight_info}")

            parts.append("")

        return "\n".join(parts)

    def stats(self) -> dict[str, Any]:
        """Retorna métricas do grafo."""
        conn = self._get_conn()
        entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

        top_entities = conn.execute(
            "SELECT name, type, mention_count FROM entities ORDER BY mention_count DESC LIMIT 10"
        ).fetchall()

        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "top_entities": [dict(r) for r in top_entities],  # type: ignore[arg-type]
        }

    # --- Extração via LLM ---

    async def ingest(self, text: str, demand_id: str = "") -> None:
        """Extrai entidades e relações do texto via LLM (fire-and-forget).

        Respeita throttle por demand_id. Falhas são logadas sem interromper.
        """
        if not self._extract_fn or not text or not text.strip():
            return

        # Throttle por demand_id
        if demand_id:
            last = self._last_ingest.get(demand_id, 0)
            if time.monotonic() - last < self.THROTTLE_SECONDS:
                logger.debug("Throttle: ingestão ignorada para demand %s", demand_id)
                return
            self._last_ingest[demand_id] = time.monotonic()

        # Dispara em background
        asyncio.create_task(self._ingest_async(text, demand_id))

    async def _ingest_async(self, text: str, demand_id: str) -> None:
        """Execução async da ingestão — não bloqueia fluxo principal."""
        try:
            existing = self._get_existing_entities_summary()
            prompt = _EXTRACTION_PROMPT.format(
                entity_types=", ".join(sorted(ENTITY_TYPES)),
                relation_types=", ".join(sorted(RELATION_TYPES)),
                existing_entities=existing or "(grafo vazio)",
                text=text[:3000],  # Limita texto para evitar prompt muito longo
            )

            if not self._extract_fn:
                return
            raw = await self._extract_fn(prompt)
            if not raw:
                return

            data = self._parse_extraction(raw)
            if not data:
                return

            self._persist_extraction(data, demand_id)
            logger.info(
                "Grafo: +%d entidades, +%d relacoes (demand: %s)",
                len(data.get("entities", [])),
                len(data.get("relations", [])),
                demand_id or "?",
            )
        except Exception as e:
            logger.warning("Falha na ingestão do grafo: %s", e)

    def _get_existing_entities_summary(self) -> str:
        """Retorna lista de entidades existentes para o prompt de extração."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name, type FROM entities ORDER BY mention_count DESC LIMIT 100"
        ).fetchall()
        if not rows:
            return ""
        return "\n".join(f"- {r['name']} ({r['type']})" for r in rows)

    def _parse_extraction(self, raw: str) -> dict[str, Any] | None:
        """Parseia e valida JSON da extração LLM."""
        # Tenta extrair JSON do texto (pode ter texto antes/depois)
        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            logger.warning("Extração sem JSON válido")
            return None

        try:
            data = json.loads(raw[start:end])
        except json.JSONDecodeError as e:
            logger.warning("JSON inválido na extração: %s", e)
            return None

        # Valida estrutura
        entities: list[Any] = data.get("entities", [])
        relations: list[Any] = data.get("relations", [])

        if not isinstance(entities, list) or not isinstance(relations, list):
            logger.warning("Estrutura inválida na extração")
            return None

        # Filtra entidades com tipos válidos
        valid_entities: list[dict[str, Any]] = []
        for raw_e in entities:
            if not isinstance(raw_e, dict):
                continue
            ent = cast(dict[str, Any], raw_e)
            if ent.get("name") and ent.get("type") in ENTITY_TYPES:
                valid_entities.append(ent)

        # Filtra relações com tipos válidos
        valid_relations: list[dict[str, Any]] = []
        for raw_r in relations:
            if not isinstance(raw_r, dict):
                continue
            rel = cast(dict[str, Any], raw_r)
            if rel.get("from") and rel.get("to") and rel.get("type") in RELATION_TYPES:
                valid_relations.append(rel)

        if not valid_entities and not valid_relations:
            return None

        return {"entities": valid_entities, "relations": valid_relations}

    def _persist_extraction(self, data: dict[str, Any], demand_id: str) -> None:
        """Persiste entidades e relações extraídas."""
        entity_types: dict[str, str] = {}

        for ent in data.get("entities", []):
            name = ent["name"]
            etype = ent["type"]
            desc = ent.get("description", "")
            self.add_entity(name, etype, desc, demand_id)
            entity_types[self._normalize_name(name)] = etype

        for rel in data.get("relations", []):
            from_name = self._normalize_name(rel["from"])
            to_name = self._normalize_name(rel["to"])

            # Resolve tipos das entidades
            from_type = entity_types.get(from_name) or self._lookup_entity_type(from_name)
            to_type = entity_types.get(to_name) or self._lookup_entity_type(to_name)

            if from_type and to_type:
                self.add_relation(
                    from_name,
                    from_type,
                    to_name,
                    to_type,
                    rel["type"],
                    rel.get("evidence", ""),
                    demand_id,
                )

    def _lookup_entity_type(self, name: str) -> str | None:
        """Busca tipo de entidade existente pelo nome."""
        conn = self._get_conn()
        row = conn.execute("SELECT type FROM entities WHERE name = ?", (name,)).fetchone()
        return row["type"] if row else None

    # --- Pruning ---

    def prune(self) -> int:
        """Remove entidades e relações antigas/pouco usadas. Retorna total removido."""
        conn = self._get_conn()
        removed = 0

        # Remove relações com peso <= 0
        result = conn.execute("DELETE FROM relations WHERE weight <= 0")
        removed += result.rowcount

        # Remove entidades antigas com mention_count=1
        cutoff = datetime.now(timezone.utc)
        cutoff_iso = cutoff.isoformat()
        result = conn.execute(
            "DELETE FROM entities WHERE mention_count <= 1 "
            "AND julianday(?) - julianday(first_seen) > ?",
            (cutoff_iso, self.PRUNE_AGE_DAYS),
        )
        removed += result.rowcount

        # Se ainda acima do limite, remove os menos usados
        entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        if entity_count > self.MAX_ENTITIES:
            excess = entity_count - self.MAX_ENTITIES
            conn.execute(
                "DELETE FROM entities WHERE id IN ("
                "  SELECT id FROM entities ORDER BY mention_count ASC, first_seen ASC LIMIT ?"
                ")",
                (excess,),
            )
            removed += excess

        relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        if relation_count > self.MAX_RELATIONS:
            excess = relation_count - self.MAX_RELATIONS
            conn.execute(
                "DELETE FROM relations WHERE id IN ("
                "  SELECT id FROM relations ORDER BY weight ASC, timestamp ASC LIMIT ?"
                ")",
                (excess,),
            )
            removed += excess

        # Limpa relações órfãs (entidades removidas)
        result = conn.execute(
            "DELETE FROM relations WHERE "
            "from_id NOT IN (SELECT id FROM entities) OR "
            "to_id NOT IN (SELECT id FROM entities)"
        )
        removed += result.rowcount

        conn.commit()

        if removed > 0:
            logger.info("Grafo: pruning removeu %d itens", removed)
        return removed

    def _prune_if_needed(self) -> None:
        """Roda pruning se limites foram atingidos."""
        conn = self._get_conn()
        entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

        if entity_count > self.MAX_ENTITIES or relation_count > self.MAX_RELATIONS:
            self.prune()

    # --- Utilitários ---

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normaliza nome de entidade: lowercase, strip."""
        if not name:
            return ""
        return name.strip().lower()

    def count(self) -> tuple[int, int]:
        """Retorna (entidades, relações)."""
        conn = self._get_conn()
        entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        relations = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        return entities, relations

    def close(self) -> None:
        """Fecha conexão com o banco."""
        if self._conn:
            self._conn.close()
            self._conn = None
