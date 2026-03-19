# Proposal: Preset Helpdesk

## Why

O ai-squad tem presets de desenvolvimento (`dev-openspec`), infra (`infra-monitor`) e investimentos (`investment-analysis`). Falta um preset de **atendimento/suporte** — um dos casos de uso mais naturais para agentes de IA.

Suporte interno é um cenário onde a plataforma brilha: chamados se repetem, documentação existe mas ninguém consulta, e o conhecimento acumulado se perde. Um squad de atendimento com **memória persistente** e **aprendizado por reforço** (reações 👍/👎) resolve isso.

## What Changes

### Novo preset `helpdesk`

Preset com 2 agentes especializados + Squad Lead, knowledge base versionada em git, busca plugável (FTS5 padrão / qmd opcional), e sistema de reforço por reações do Telegram.

### Fluxo principal

```
Usuário abre chamado (Telegram)
         │
         ▼
┌─────────────────┐
│   Squad Lead    │  Classifica: chamado ou ingestão de doc?
│   (Triagem)     │
└────────┬────────┘
     ┌───┴───────────────┐
     │                   │
     ▼                   ▼
┌──────────┐      ┌──────────────┐
│ Atendente│      │ Base Conhec. │
│          │      │              │
│ 1. Busca │      │ 1. Recebe    │
│    KB    │      │    arquivo   │
│ 2. Resp. │      │ 2. Converte  │
│ 3. Salva │      │    → .md     │
│    se    │      │ 3. Indexa    │
│    novo  │      │ 4. Commit    │
└────┬─────┘      └──────────────┘
     │
     │ Não resolveu?
     ▼
┌──────────┐
│ Escalação│  checkpoint → humano
└──────────┘
     │
     │ Humano resolve
     ▼
Atendente registra solução na KB
(próxima vez, resolve automaticamente)
```

### Reforço por reações

```
Agente responde → Usuário reage 👍 ou 👎
     │
     ▼
👍 → Incrementa score do documento fonte (priorizado em buscas futuras)
👎 → Marca documento para revisão (score decrementado)
```

### Knowledge base (versionada em git)

```
knowledge/
├── atendimentos/         ← soluções de chamados resolvidos
│   └── vpn-nao-conecta-2026-03-18.md
├── documentacao/         ← docs dos sistemas (inseridos pelo agente base-conhecimento)
│   ├── sistemas/
│   ├── processos/
│   └── faq/
└── knowledge.db          ← índice FTS5 (ou qmd se habilitado)
```

### Busca plugável

- **Padrão**: SQLite FTS5 (zero dependências externas, inspirado no `LessonsStore` existente)
- **Opcional**: qmd (busca semântica com embeddings locais, requer Node.js)

## Capabilities

### atendente-agent
Agente de primeiro nível que recebe chamados, busca na knowledge base por soluções similares, responde ao usuário e registra novas soluções quando resolve algo inédito. Aceita texto, fotos (screenshots de erro), voz e documentos.

### base-conhecimento-agent
Agente de ingestão de documentação que recebe arquivos (PDF, DOCX, MD, imagens com texto), converte para Markdown estruturado, indexa na knowledge base e faz git commit. Alimenta a base que o Atendente consulta.

### helpdesk-squad-lead
Squad Lead especializado em triagem de atendimento. Classifica se a mensagem é um chamado (→ Atendente) ou ingestão de documento (→ Base Conhecimento). Gerencia escalação para humano quando necessário.

### knowledge-store
Módulo de busca na knowledge base com interface plugável (FTS5 ou qmd). Suporta score de reforço (👍/👎) para priorizar documentos validados por usuários. Similar ao `LessonsStore` mas orientado a documentos Markdown completos.

### reaction-tracker
Captura reações do Telegram (`message_reaction`), mapeia para o documento fonte usado na resposta, e atualiza o score no frontmatter do .md correspondente.

### document-ingest
Pipeline de conversão de documentos: PDF → texto (pdfplumber), DOCX → markdown, imagem → texto (descrição via LLM), texto puro → markdown estruturado. Salva em `knowledge/documentacao/` com metadados.

## Impact

### Arquivos novos
- `src/presets/helpdesk/pipeline/pipeline.yaml`
- `src/presets/helpdesk/pipeline/steps/step-01-busca-kb.md`
- `src/presets/helpdesk/pipeline/steps/step-02-atendimento.md`
- `src/presets/helpdesk/pipeline/steps/step-03-escalacao.md`
- `src/presets/helpdesk/pipeline/steps/step-04-registro.md`
- `src/presets/helpdesk/agents/squad-lead/AGENTS.md`
- `src/presets/helpdesk/agents/atendente/AGENTS.md`
- `src/presets/helpdesk/agents/base-conhecimento/AGENTS.md`
- `src/presets/helpdesk/knowledge/` (diretório inicial vazio)

### Módulos novos no core
- `src/orchestrator/knowledge.py` — busca plugável (FTS5/qmd) com score de reforço
- `src/orchestrator/ingest.py` — conversão de documentos para markdown
- `src/messaging/telegram.py` — handler de `message_reaction` (extensão)

### Sem impacto
- Engine, daemon, CLI, adapters — funcionam com o novo preset sem mudança
- Presets existentes — sem alteração

## Non-Goals

- Fila de atendimento com prioridade/SLA — por enquanto é first-come-first-served
- Atendimento multi-canal (email, WhatsApp) — apenas Telegram
- Dashboard de métricas de atendimento — futuro
- OCR avançado em imagens — usa descrição via LLM
- Integração com sistemas de tickets externos (Jira, Zendesk)
