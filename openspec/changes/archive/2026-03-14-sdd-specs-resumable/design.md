## Context

O ai-dev-team orquestra agentes PO, Dev e QA via Telegram. Hoje os agentes operam sem memória do produto, os artefatos gerados ficam apenas na resposta do LLM (não persistem), e se o container reiniciar toda a conversa é perdida. Isso limita a utilidade real do time.

## Goals / Non-Goals

**Goals:**
- Agentes produzem artefatos SDD versionáveis no repositório do projeto
- PO entende o produto antes de especificar (lê README, estrutura, specs existentes)
- Conversa agente ↔ usuário é persistida e retomável após crash
- Daemon retoma demandas incompletas no startup

**Non-Goals:**
- Editor visual de specs (v1 é arquivos markdown)
- Merge automático de specs com conflito
- Versionamento semântico de specs
- Persistência em banco de dados (v1 usa JSON/arquivos)

## Decisions

### 1. Artefatos SDD no workspace do projeto

**Escolha**: PO gera artefatos em `/workspace/specs/<demand-id>/` (proposal.md, design.md, etc.)

**Alternativas**: Salvar em state/, salvar em diretório separado

**Razão**: Dentro do repo permite versionamento via git, revisão via PR, e serve como documentação viva. O dev agent já tem acesso ao `/workspace`.

### 2. Contexto do produto via leitura de arquivos

**Escolha**: Antes de cada interação com o PO, o engine coleta contexto do projeto: README.md, estrutura de diretórios (2 níveis), e specs existentes. Esse contexto é injetado no prompt.

**Alternativas**: Deixar o agente explorar sozinho via tools, indexar o repo inteiro

**Razão**: Injetar no prompt é previsível e rápido. O agente explorando sozinho consome tokens desnecessários. Indexação completa é complexa demais para v1.

### 3. Persistência de conversa em JSON

**Escolha**: Cada demanda salva seu histórico em `state/<demand-id>/conversation.json` — lista de mensagens com role (agent/user), conteúdo e timestamp.

**Alternativas**: SQLite, salvar no repo, Redis

**Razão**: JSON é consistente com o StateManager existente. Escrita atômica (temp + rename) já está implementada. Não precisa de dependência externa.

### 4. Checkpoint por etapa no estado da demanda

**Escolha**: O state da demanda salva o checkpoint atual (ex: `{"state": "po_working", "phase": "conversation", "turn": 3}`) e o resultado parcial de cada fase.

**Alternativas**: Salvar apenas estado bruto, usar write-ahead log

**Razão**: Checkpoint granular permite retomar do ponto exato. Se o container caiu durante conversa com PO no turno 3, ao reiniciar o PO recebe o histórico dos turnos 1-3 e continua.

### 5. AGENTS.md com instruções de exploração

**Escolha**: O AGENTS.md do PO instrui o agente a primeiro explorar o repo (ler README, listar pastas, verificar specs existentes) antes de fazer perguntas ao usuário.

**Alternativas**: Hardcodar no engine, criar tool específica

**Razão**: O AGENTS.md é a fonte de persona do agente — colocar as instruções lá permite que o usuário customize o comportamento de exploração editando `~/.ai-dev-team/teams/<nome>/agents/po/AGENTS.md`.

## Risks / Trade-offs

**[Contexto do projeto grande demais]** → Mitigação: limitar leitura a README.md + tree 2 níveis + specs/. Se ultrapassar 4000 tokens, truncar.

**[Histórico de conversa longo]** → Mitigação: manter últimas N mensagens (ex: 20) no contexto, resumir as anteriores.

**[Retomada com estado inconsistente]** → Mitigação: validar estado no startup. Se estado é inválido, notificar via Telegram e marcar como erro.

**[Artefatos no workspace podem conflitar]** → Mitigação: cada demanda usa subdiretório próprio (`specs/<demand-id>/`). Sem sobreposição.
