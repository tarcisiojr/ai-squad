# Design: Preset Helpdesk

## Visão geral da arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    TELEGRAM                              │
│  texto │ voz │ foto │ documento │ reação 👍/👎          │
└────────┬───────────────────────────┬────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐          ┌──────────────────┐
│ TelegramMsgBus  │          │ ReactionHandler  │ ← NOVO
│ (existente)     │          │ (extensão)       │
└────────┬────────┘          └────────┬─────────┘
         │                            │
         ▼                            ▼
┌─────────────────┐          ┌──────────────────┐
│   Squad Lead    │          │ ReactionTracker  │ ← NOVO
│   (helpdesk)    │          │ msg_id → doc_path│
└───┬─────────┬───┘          └────────┬─────────┘
    │         │                       │
    ▼         ▼                       ▼
┌────────┐ ┌──────────────┐  ┌──────────────────┐
│Atenden.│ │Base Conhec.  │  │ KnowledgeStore   │ ← NOVO
│        │ │              │  │ (FTS5 / qmd)     │
│ busca→ │ │ ingest →     │  └──────────────────┘
│ respond│ │ converte →   │           ▲
│ salva  │ │ indexa →     │           │
│        │ │ commit       │  ┌──────────────────┐
└────────┘ └──────────────┘  │ DocumentIngest   │ ← NOVO
                             │ pdf/docx/img→md  │
                             └──────────────────┘
```

## Decisões de design

### 1. KnowledgeStore como evolução do LessonsStore

O `LessonsStore` existente usa SQLite FTS5 para lições aprendidas. O `KnowledgeStore` segue o mesmo padrão mas para documentos Markdown completos:

```python
# Interface plugável
class KnowledgeBackend(ABC):
    def index(self, doc_path: Path) -> None: ...
    def search(self, query: str, limit: int = 5) -> list[KnowledgeResult]: ...
    def reindex_all(self) -> None: ...

class FTS5Backend(KnowledgeBackend):
    """Padrão — zero dependências externas."""

class QmdBackend(KnowledgeBackend):
    """Opcional — busca semântica via qmd CLI."""
```

**Decisão**: Não herdar de LessonsStore. São domínios diferentes — lições são registros curtos (problema/solução), knowledge são documentos completos com frontmatter e hierarquia.

**Decisão**: FTS5 indexa título + conteúdo + tags do frontmatter. Score de reforço é aplicado como boost no ranking (`rank * (1 + score * 0.1)`).

### 2. Score de reforço no frontmatter

O score vive no frontmatter do próprio .md — assim é versionado em git e auditável:

```markdown
---
score: 7
tags: [vpn, rede]
created: 2026-03-18
---
```

**Decisão**: Usar frontmatter YAML (não banco) porque:
- Versionável em git (histórico de score)
- Legível por humanos
- Portável (copiar .md entre times carrega o score)
- qmd já lê frontmatter nativamente

### 3. ReactionTracker com mapeamento em memória

```python
class ReactionTracker:
    _msg_to_doc: dict[int, str]  # msg_id → doc_path (LRU, max 10k)
    _knowledge: KnowledgeStore

    def track(self, msg_id: int, doc_path: str) -> None:
        """Registra qual doc gerou a resposta de msg_id."""

    def on_reaction(self, msg_id: int, emoji: str) -> None:
        """Atualiza score do doc baseado na reação."""
```

**Decisão**: Mapeamento em memória (não persistido). Se o bot reiniciar, perde mapeamentos pendentes — aceitável porque reações geralmente chegam em minutos. Evita complexidade de persistência adicional.

### 4. DocumentIngest modular por tipo

```python
class DocumentIngest:
    _converters: dict[str, Callable]  # extensão → função de conversão

    def ingest(self, file_path: Path, category: str = "") -> Path:
        """Converte documento para .md e salva em knowledge/."""
```

Converters:
- `.pdf` → pdfplumber (texto) — dependência opcional, fallback para PyPDF2
- `.docx` → python-docx + conversão manual
- `.md` → cópia direta + frontmatter
- `.txt` → wrapping em markdown
- `.jpg/.png` → descrição via LLM (prompt: "Descreva este screenshot de suporte técnico")

**Decisão**: pdfplumber e python-docx como dependências opcionais. Se não instalados, agente informa: "Instale pdfplumber para suporte a PDF: pip install pdfplumber".

### 5. Pipeline sem step de busca separado

Originalmente pensamos em step `busca-kb` separado. Mas a busca é **parte do contexto do Atendente**, não um step independente:

```yaml
# pipeline.yaml
steps:
  - id: atendimento
    name: "Atendimento"
    agent: atendente
    type: agent
    execution: subagent
    model_tier: powerful
    file: steps/step-01-atendimento.md

  - id: escalacao
    name: "Escalação"
    agent: atendente
    type: checkpoint
    execution: subagent
    model_tier: fast
    file: steps/step-02-escalacao.md

  - id: registro
    name: "Registro de Solução"
    agent: atendente
    type: agent
    execution: inline
    model_tier: fast
    file: steps/step-03-registro.md
```

**Decisão**: Busca na KB é feita pelo `prompt_builder` antes de montar o prompt do Atendente — injeta contexto relevante da KB no prompt. Isso é mais natural que um step separado e reaproveita o mecanismo de lições.

### 6. Squad Lead com roteamento por tipo de input

```
texto normal → Atendente (chamado)
arquivo/documento → Base Conhecimento (ingestão)
"status" / "quantos chamados" → resposta direta
```

**Decisão**: O Squad Lead do helpdesk não segue pipeline linear para ingestão de documentos. Ingestão é uma "side mission" — delega direto ao agente base-conhecimento, sem passar pelo pipeline de atendimento.

### 7. Handler de documentos no Telegram

O TelegramMessageBus já tem handlers para texto, voz e foto. Falta handler para `document` (arquivos genéricos):

```python
# Extensão em telegram.py
async def _handle_document(update, context):
    """Recebe PDFs, DOCX, etc enviados como arquivo."""
    ...
    await self._document_callback(caption, tmp_path, ...)
```

E handler para `message_reaction`:
```python
from telegram.ext import MessageReactionHandler

async def _handle_reaction(update, context):
    """Captura reações em mensagens do bot."""
    ...
    await self._reaction_callback(chat_id, msg_id, emoji, user_id)
```

### 8. Git commit automático

O agente base-conhecimento usa MCP tool `filesystem` (já disponível via Claude Agent SDK) para salvar arquivos. Após salvar, executa git commit via ferramenta bash.

**Decisão**: Commit é feito pelo agente, não pelo core. O agente tem autonomia para commitar no repositório do time. Mensagem padronizada: `docs: <nome-do-doc> (<fonte>)`.

## Dependências

| Módulo | Dependência | Obrigatória |
|--------|------------|-------------|
| KnowledgeStore (FTS5) | sqlite3 (stdlib) | Sim |
| KnowledgeStore (qmd) | qmd CLI + Node.js | Não |
| DocumentIngest (PDF) | pdfplumber | Não |
| DocumentIngest (DOCX) | python-docx | Não |
| ReactionTracker | python-telegram-bot 21+ | Sim (já existente) |

## Riscos

- **python-telegram-bot `message_reaction`**: Verificar se a versão atual suporta `MessageReactionHandler`. Se não, pode ser necessário usar raw updates.
- **Frontmatter parsing**: Usar `pyyaml` (já é dependência) para ler/escrever frontmatter. Cuidado com encoding UTF-8.
- **Git conflicts**: Se múltiplos agentes commitam ao mesmo tempo, pode haver conflito. Mitigação: atomic_write + lock no commit.
