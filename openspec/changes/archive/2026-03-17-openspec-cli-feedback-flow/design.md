## Context

O ai-dev-team tem o CLI openspec instalado no container Docker e disponivel no PATH. Os agentes devem usar esse CLI para criar e gerenciar artefatos SDD em vez de criar arquivos manualmente. O fluxo completo (proposal → specs → design → tasks → implementacao) deve ser respeitado.

## Goals / Non-Goals

**Goals:**
- Agentes usam openspec CLI para criar changes e artefatos
- Fluxo SDD completo respeitado (nada pulado)
- Feedback visivel no Telegram durante execucao
- Squad Lead valida existencia dos artefatos antes de avancar

**Non-Goals:**
- Mudar o CLI openspec em si
- Criar UI para o fluxo
- Automatizar aprovacao de artefatos

## Decisions

### 1. Agentes usam openspec CLI via tools do SDK

Os agentes ja tem acesso ao terminal via Claude Agent SDK. Eles podem executar `openspec new change`, `openspec instructions`, etc. diretamente. Nao precisa de tool customizada — o SDK ja suporta execucao de comandos.

As instrucoes vao no AGENTS.md de cada agente.

### 2. Fluxo do Squad Lead com validacao

```
1. Squad Lead recebe demanda
2. Invoca PO para especificar
3. PO usa openspec: new change → proposal → specs → design → tasks
4. Squad Lead valida: todos os artefatos existem?
5. Se sim, invoca Dev com o tasks.md
6. Dev implementa task por task
7. Squad Lead invoca QA para validar
8. QA valida contra specs
```

O Squad Lead verifica os artefatos usando `openspec status --change <nome>` antes de avancar.

### 3. Feedback periodico no engine

O engine envia mensagem ao Telegram a cada 30 segundos durante execucao de um agente:
- "PO trabalhando na especificacao... (45s)"
- "Dev implementando... (2min)"

Implementado como task em background que roda junto com o dispatch.

### 4. AGENTS.md como unica fonte de instrucao

Toda a logica de como usar o openspec vai nos AGENTS.md. O codigo do engine nao muda alem do feedback. Os agentes aprendem a usar o openspec via instrucoes no AGENTS.md.

## Risks / Trade-offs

**[Agente pode ignorar instrucoes do AGENTS.md]** → Mitigacao: instrucoes claras e repetidas. Squad Lead valida artefatos antes de avancar.

**[openspec CLI pode nao estar no PATH no Docker]** → Mitigacao: instalado via pip no Dockerfile. Verificar.

**[Feedback pode poluir o chat]** → Mitigacao: mensagens curtas, a cada 30s, sem repetir a mesma.
