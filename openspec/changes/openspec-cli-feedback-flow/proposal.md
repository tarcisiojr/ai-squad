## Why

Os agentes criam artefatos manualmente (escrevendo arquivos direto) em vez de usar o CLI openspec instalado no projeto. O fluxo SDD não é respeitado — o PO gera proposal e o Dev já começa a implementar, pulando specs e design. Além disso, durante execuções longas o usuário fica sem feedback no Telegram, sem saber se o sistema travou ou está trabalhando.

## What Changes

- **AGENTS.md do Squad Lead reescrito** — instrui o Squad Lead a usar o CLI openspec para criar changes, gerar artifacts (proposal, specs, design, tasks), e seguir o fluxo completo antes de implementar
- **AGENTS.md do PO reescrito** — instrui o PO a usar `openspec new change`, `openspec instructions proposal`, gerar proposal.md, depois specs/, depois design.md seguindo as instrucoes do CLI
- **AGENTS.md do Dev reescrito** — instrui o Dev a só implementar quando tasks.md existir, ler tasks e implementar uma por vez
- **Feedback periódico no Telegram** — engine envia atualizações ao usuário durante execuções longas (ex: "PO gerando especificação...", "Dev implementando task 3/7...")
- **Squad Lead valida fluxo** — antes de passar pro Dev, valida que proposal + specs + design + tasks existem no diretório da demanda

## Capabilities

### New Capabilities
- `openspec-agent-integration`: Agentes usam o CLI openspec para criar e gerenciar artefatos SDD no workspace do projeto
- `execution-feedback`: Engine envia feedback periódico ao Telegram durante execuções longas, informando qual agente está trabalhando e o que está fazendo

### Modified Capabilities
- `orchestrator`: Engine envia feedback periódico ao usuário durante dispatch de agentes

## Impact

- **agents/squad-lead/AGENTS.md** — reescrever com instrucoes de uso do openspec CLI e validacao do fluxo
- **agents/po/AGENTS.md** — reescrever com instrucoes de uso do openspec CLI para gerar artefatos
- **agents/dev/AGENTS.md** — reescrever com instrucoes de ler tasks.md e implementar task por task
- **agents/qa/AGENTS.md** — ajustar para validar contra specs gerados pelo openspec
- **engine.py** — adicionar feedback periodico ao Telegram durante dispatch_agent
