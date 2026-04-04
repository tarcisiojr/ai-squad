"""Knowledge Store — busca plugável em base de conhecimento Markdown.

Suporta dois backends:
- FTS5Backend (padrão): SQLite FTS5, zero dependências externas
- QmdBackend (opcional): busca semântica via qmd CLI

Documentos .md com frontmatter YAML (score, tags, created) são indexados
e podem ser buscados por relevância. Score de reforço (👍/👎) influencia
o ranking.
"""

import hashlib
import logging
import re
import shutil
import sqlite3
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from ai_squad.orchestrator.atomic_write import write_text_atomic

logger = logging.getLogger("ai-squad.knowledge")

# Regex para extrair frontmatter YAML
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class KnowledgeResult:
    """Resultado de busca na knowledge base."""

    path: str
    title: str
    snippet: str
    score: int = 0
    used_count: int = 0
    relevance: float = 0.0


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extrai frontmatter YAML e corpo do documento."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    meta: dict[str, Any] = {}
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        pass
    body = content[match.end() :]
    return meta, body


def update_frontmatter(content: str, updates: dict[str, Any]) -> str:
    """Atualiza campos do frontmatter mantendo o resto do documento."""
    meta, body = parse_frontmatter(content)
    meta.update(updates)
    yaml_str = yaml.dump(meta, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}"


def _extract_title(body: str) -> str:
    """Extrai título do primeiro heading do Markdown."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _content_hash(text: str) -> str:
    """Hash curto do conteúdo para detectar mudanças."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


# --- ABC ---


class KnowledgeBackend(ABC):
    """Interface abstrata para backends de busca."""

    @abstractmethod
    def index(self, doc_path: Path) -> None:
        """Indexa um documento Markdown."""
        ...

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[KnowledgeResult]:
        """Busca documentos relevantes."""
        ...

    @abstractmethod
    def reindex_all(self) -> None:
        """Reindexa todos os documentos."""
        ...

    @abstractmethod
    def remove(self, doc_path: Path) -> None:
        """Remove documento do índice."""
        ...


# --- FTS5 Backend ---


class FTS5Backend(KnowledgeBackend):
    """Backend de busca usando SQLite FTS5.

    Indexa título, conteúdo, tags e aplica boost por score de reforço.
    """

    def __init__(self, knowledge_dir: Path) -> None:
        self._knowledge_dir = knowledge_dir
        self._db_path = knowledge_dir / "knowledge.db"
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Retorna conexão SQLite (lazy, reusa)."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Cria tabelas se não existirem."""
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                title TEXT DEFAULT '',
                content TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                score INTEGER DEFAULT 0,
                used_count INTEGER DEFAULT 0,
                content_hash TEXT DEFAULT '',
                indexed_at TEXT DEFAULT (datetime('now'))
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                title,
                content,
                tags,
                content='documents',
                content_rowid='id',
                tokenize='unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documents BEGIN
                INSERT INTO docs_fts(rowid, title, content, tags)
                VALUES (new.id, new.title, new.content, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documents BEGIN
                INSERT INTO docs_fts(docs_fts, rowid, title, content, tags)
                VALUES ('delete', old.id, old.title, old.content, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON documents BEGIN
                INSERT INTO docs_fts(docs_fts, rowid, title, content, tags)
                VALUES ('delete', old.id, old.title, old.content, old.tags);
                INSERT INTO docs_fts(rowid, title, content, tags)
                VALUES (new.id, new.title, new.content, new.tags);
            END;
        """)
        conn.commit()

    def index(self, doc_path: Path) -> None:
        """Indexa um documento Markdown (incremental — pula se hash igual)."""
        if not doc_path.exists():
            return
        try:
            raw = doc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            logger.warning("Erro ao ler documento: %s", doc_path)
            return

        content_hash = _content_hash(raw)
        meta, body = parse_frontmatter(raw)
        title = _extract_title(body) or doc_path.stem
        raw_tags: Any = meta.get("tags", [])
        typed_tags: list[Any] = cast(list[Any], raw_tags) if isinstance(raw_tags, list) else [raw_tags]
        tags_str: str = " ".join(str(t) for t in typed_tags)
        score = int(meta.get("score", 0))
        rel_path = str(doc_path.relative_to(self._knowledge_dir))

        conn = self._get_conn()

        # Verifica se já existe e se o hash mudou
        existing = conn.execute(
            "SELECT id, content_hash FROM documents WHERE path = ?",
            (rel_path,),
        ).fetchone()

        if existing and existing["content_hash"] == content_hash:
            return  # Nada mudou

        if existing:
            conn.execute(
                "UPDATE documents SET title=?, content=?, tags=?, score=?, content_hash=?, "
                "indexed_at=datetime('now') WHERE id=?",
                (title, body, tags_str, score, content_hash, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO documents (path, title, content, tags, score, content_hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (rel_path, title, body, tags_str, score, content_hash),
            )
        conn.commit()

    def search(self, query: str, limit: int = 5) -> list[KnowledgeResult]:
        """Busca documentos via FTS5 com boost por score de reforço."""
        conn = self._get_conn()

        if not query or not query.strip():
            return []

        # Prepara query FTS5
        words: list[str] = []
        for word in query.lower().split():
            clean = "".join(c for c in word if c.isalnum())
            if len(clean) >= 3:
                words.append(clean)

        if not words:
            return []

        fts_query = " OR ".join(words[:15])
        try:
            rows = conn.execute(
                "SELECT d.*, rank FROM documents d "
                "JOIN docs_fts ON d.id = docs_fts.rowid "
                "WHERE docs_fts MATCH ? "
                "ORDER BY (rank * (1.0 + d.score * 0.1)) "
                "LIMIT ?",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            logger.warning("Query FTS5 inválida: %s", fts_query)
            return []

        results: list[KnowledgeResult] = []
        for row in rows:
            content = str(row["content"] or "")
            # Gera snippet: primeiras linhas não-vazias
            snippet_lines = [
                line.strip()
                for line in content.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ][:3]
            snippet = " ".join(snippet_lines)[:300]

            results.append(
                KnowledgeResult(
                    path=str(row["path"]),
                    title=str(row["title"] or ""),
                    snippet=snippet,
                    score=int(row["score"] or 0),
                    used_count=int(row["used_count"] or 0),
                    relevance=abs(float(row["rank"])) if row["rank"] else 0.0,
                )
            )

        return results

    def reindex_all(self) -> None:
        """Reindexa todos os .md da knowledge base."""
        conn = self._get_conn()
        conn.execute("DELETE FROM documents")
        conn.commit()

        for md_file in self._knowledge_dir.rglob("*.md"):
            self.index(md_file)

        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        logger.info("Reindexados %d documentos na knowledge base", count)

    def remove(self, doc_path: Path) -> None:
        """Remove documento do índice."""
        try:
            rel_path = str(doc_path.relative_to(self._knowledge_dir))
        except ValueError:
            rel_path = str(doc_path)
        conn = self._get_conn()
        conn.execute("DELETE FROM documents WHERE path = ?", (rel_path,))
        conn.commit()

    def update_score(self, rel_path: str, delta: int) -> None:
        """Atualiza score de um documento no índice (e no frontmatter do .md)."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, score FROM documents WHERE path = ?",
            (rel_path,),
        ).fetchone()
        if not row:
            return

        new_score = max(0, (row["score"] or 0) + delta)
        conn.execute("UPDATE documents SET score = ? WHERE id = ?", (new_score, row["id"]))
        conn.commit()

        # Atualiza frontmatter do arquivo
        full_path = self._knowledge_dir / rel_path
        if full_path.exists():
            try:
                content = full_path.read_text(encoding="utf-8")
                updated = update_frontmatter(content, {"score": new_score})
                write_text_atomic(full_path, updated)
                logger.info("Score atualizado: %s → %d", rel_path, new_score)
            except Exception as e:
                logger.warning("Erro ao atualizar frontmatter de %s: %s", rel_path, e)

    def increment_used(self, rel_path: str) -> None:
        """Incrementa contador de uso de um documento."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE documents SET used_count = used_count + 1 WHERE path = ?",
            (rel_path,),
        )
        conn.commit()

    def count(self) -> int:
        """Retorna total de documentos indexados."""
        conn = self._get_conn()
        return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def close(self) -> None:
        """Fecha conexão com o banco."""
        if self._conn:
            self._conn.close()
            self._conn = None


# --- Qmd Backend ---


class QmdBackend(KnowledgeBackend):
    """Backend de busca semântica via qmd CLI.

    Requer qmd instalado no PATH (npm install -g @tobilu/qmd).
    Usa subprocess para interagir com o CLI.
    """

    def __init__(self, knowledge_dir: Path) -> None:
        self._knowledge_dir = knowledge_dir
        # Nome único baseado no caminho — evita colisão entre times/testes
        slug = str(knowledge_dir).replace("/", "_").replace("\\", "_").strip("_")[-60:]
        self._collection_name = f"kb-{slug}"
        self._initialized = False
        self._has_embeddings: bool | None = None

    def _ensure_collection(self) -> None:
        """Garante que a collection qmd existe."""
        if self._initialized:
            return
        try:
            subprocess.run(
                [
                    "qmd",
                    "collection",
                    "add",
                    str(self._knowledge_dir),
                    "--name",
                    self._collection_name,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self._initialized = True
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning("Falha ao inicializar qmd collection: %s", e)

    def index(self, doc_path: Path) -> None:
        """Atualiza índice e tenta gerar embeddings."""
        self._ensure_collection()
        # Atualiza índice de texto
        try:
            subprocess.run(
                ["qmd", "update"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning("Falha ao atualizar índice qmd: %s", e)

        # Tenta embeddings (tolerante a falha)
        try:
            result = subprocess.run(
                ["qmd", "embed", "-c", self._collection_name],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                self._has_embeddings = True
            else:
                self._has_embeddings = False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._has_embeddings = False

    def _check_embeddings(self) -> bool:
        """Verifica se embeddings estão disponíveis (cacheado)."""
        if self._has_embeddings is not None:
            return self._has_embeddings
        try:
            result = subprocess.run(
                ["qmd", "status"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            # Se "Pending: 0" ou "Vectors: N" (N>0), embeddings ok
            output = result.stdout
            if "Pending:  0" in output:
                self._has_embeddings = True
            elif "need embedding" in output:
                self._has_embeddings = False
            else:
                # Conservador: assume sem embeddings
                self._has_embeddings = False
        except Exception:
            self._has_embeddings = False
        return self._has_embeddings

    def search(self, query: str, limit: int = 5) -> list[KnowledgeResult]:
        """Busca via qmd. Usa 'query' (híbrido) se embeddings ok, senão 'search' (BM25)."""
        if not query or not query.strip():
            return []

        self._ensure_collection()

        # Decide comando: 'query' (híbrido) ou 'search' (BM25 puro)
        if self._check_embeddings():
            cmd = ["qmd", "query", query, "-c", self._collection_name, "--json"]
        else:
            cmd = ["qmd", "search", query, "-c", self._collection_name, "--json"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning("qmd %s falhou: %s", cmd[1], result.stderr.strip()[:200])
                return []

            import json

            data: Any = json.loads(result.stdout)
            results: list[KnowledgeResult] = []
            items = cast(
                list[dict[str, Any]],
                data if isinstance(data, list) else data.get("results", []),
            )
            for item in items[:limit]:
                item_path = str(item.get("path", item.get("file", "")))
                # Lê score do frontmatter do arquivo original
                score = 0
                full_path = self._knowledge_dir / item_path
                if full_path.exists():
                    try:
                        content = full_path.read_text(encoding="utf-8")
                        meta, _ = parse_frontmatter(content)
                        score = int(meta.get("score", 0))
                    except Exception:
                        pass

                results.append(
                    KnowledgeResult(
                        path=item_path,
                        title=str(item.get("title", "")),
                        snippet=str(item.get("content", item.get("snippet", "")))[:300],
                        score=score,
                        relevance=float(item.get("score", 0)),
                    )
                )
            return results

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.warning("Falha na busca qmd: %s", e)
            return []

    def reindex_all(self) -> None:
        """Reindexa: atualiza índice de texto e tenta gerar embeddings."""
        self._ensure_collection()
        # Atualiza índice de texto (sempre funciona)
        try:
            subprocess.run(
                ["qmd", "update"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning("Falha ao atualizar índice qmd: %s", e)

        # Tenta gerar embeddings (pode falhar se sqlite-vec indisponível)
        try:
            result = subprocess.run(
                ["qmd", "embed", "-c", self._collection_name, "--force"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                self._has_embeddings = True
                logger.info("Embeddings gerados para collection %s", self._collection_name)
            else:
                self._has_embeddings = False
                logger.info(
                    "Embeddings indisponíveis (sqlite-vec?) — usando busca BM25: %s",
                    result.stderr.strip()[:100],
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self._has_embeddings = False
            logger.info("Embeddings indisponíveis — usando busca BM25: %s", e)

    def remove(self, doc_path: Path) -> None:
        """Qmd reindexação é batch — remove exige reindex completo."""
        self.reindex_all()


# --- Facade ---


class KnowledgeStore:
    """Facade para busca na knowledge base com backend plugável.

    Seleciona automaticamente o backend disponível:
    - Se qmd está no PATH e use_qmd=True → QmdBackend
    - Caso contrário → FTS5Backend (padrão)

    Gerencia score de reforço e formatação para prompt.
    """

    MAX_CONTEXT_RESULTS = 5

    def __init__(self, knowledge_dir: str | Path, use_qmd: bool = False) -> None:
        self._knowledge_dir = Path(knowledge_dir)
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)

        # Seleciona backend
        if use_qmd and shutil.which("qmd"):
            self._backend: KnowledgeBackend = QmdBackend(self._knowledge_dir)
            self._fts5: FTS5Backend | None = FTS5Backend(self._knowledge_dir)
            logger.info("Knowledge backend: qmd (semântico) + FTS5 (score)")
        else:
            self._fts5 = FTS5Backend(self._knowledge_dir)
            self._backend = self._fts5
            if use_qmd:
                logger.warning("qmd não encontrado no PATH. Usando FTS5.")
            else:
                logger.info("Knowledge backend: FTS5")

    def index(self, doc_path: Path) -> None:
        """Indexa um documento na knowledge base."""
        self._backend.index(doc_path)
        # Sempre mantém FTS5 atualizado (para score tracking)
        if self._fts5 and self._backend is not self._fts5:
            self._fts5.index(doc_path)

    def search(self, query: str, limit: int = 5) -> list[KnowledgeResult]:
        """Busca documentos relevantes."""
        return self._backend.search(query, limit=limit)

    def reindex_all(self) -> None:
        """Reindexa todos os documentos."""
        self._backend.reindex_all()
        if self._fts5 and self._backend is not self._fts5:
            self._fts5.reindex_all()

    def update_score(self, doc_path: str, delta: int) -> None:
        """Atualiza score de reforço de um documento."""
        if self._fts5:
            self._fts5.update_score(doc_path, delta)

    def increment_used(self, doc_path: str) -> None:
        """Incrementa contador de uso."""
        if self._fts5:
            self._fts5.increment_used(doc_path)

    def format_for_prompt(self, query: str) -> str:
        """Busca e formata resultados para injeção no prompt do agente."""
        results = self.search(query, limit=self.MAX_CONTEXT_RESULTS)
        if not results:
            return ""

        parts = ["## Documentos relevantes da base de conhecimento\n"]
        for r in results:
            score_badge = f" (👍 {r.score})" if r.score > 0 else ""
            parts.append(f"### {r.title}{score_badge}")
            parts.append(f"_Fonte: {r.path}_")
            if r.snippet:
                parts.append(r.snippet)
            parts.append("")

            # Incrementa uso
            self.increment_used(r.path)

        return "\n".join(parts)

    def count(self) -> int:
        """Retorna total de documentos indexados."""
        if self._fts5:
            return self._fts5.count()
        return 0

    def close(self) -> None:
        """Fecha conexões."""
        if self._fts5:
            self._fts5.close()
