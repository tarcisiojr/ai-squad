## Why

A experiência de uso via Telegram está quebrada em vários pontos: botões de aprovação aparecem quando o PO está fazendo perguntas, o Dev diz que fez mas não criou nada, a formatação é ilegível, nomes de agentes estão hardcoded no código, e não há conversa fluida com os agentes. O fluxo precisa ser reconstruído usando OpenSpec como framework, com conversas naturais, agentes que realmente executam, e configuração dinâmica.

## What Changes

- **BREAKING**: Refatorar `_agent_conversation` — separar modo conversa (sem botões) de modo aprovação (com botões), usando marcador `---SPEC_READY---` / `---DONE---` no texto do agente
- **BREAKING**: Fluxo de demanda via OpenSpec — PO gera `proposal.md` e `specs/` no formato OpenSpec; Dev lê specs e implementa de fato; QA valida contra specs
- **Conversa fluida por agente** — comandos `/<agente>` lidos dinamicamente do `config.yaml`, cada conversa mantém contexto independente
- **Nomes e labels da config** — eliminar hardcoded; ler `personas` do config.yaml para nomes, avatares e comandos
- **Web search para PO** — habilitar tool de busca web no Claude Agent SDK para o PO pesquisar quando necessário
- **Formatação Telegram** — enviar tudo como texto plano (sem parse_mode Markdown), limpar caracteres especiais
- **Feedback de progresso do Dev** — notificações periódicas durante execução longa + timeout estendido
- **Dev executa de fato** — Dev só mostra "PR pronto" quando criou branch, commits e código real no workspace

## Capabilities

### New Capabilities
- `conversation-flow`: Separação de modo conversa (livre, sem botões) e modo aprovação (com botões), controlado por marcador no texto do agente
- `dynamic-agent-commands`: Comandos `/<agente>` gerados dinamicamente a partir de `config.yaml` personas, sem hardcoding
- `agent-web-search`: Capacidade de busca web para agentes (PO) via tools do Claude Agent SDK
- `dev-progress-feedback`: Notificações de progresso durante execução longa do Dev, com timeout estendido
- `openspec-agent-flow`: Fluxo de demanda seguindo framework OpenSpec — PO gera proposal+specs, Dev lê e implementa, QA valida contra specs

### Modified Capabilities
- `orchestrator`: Engine precisa de dois modos de conversa (livre vs aprovação), ler personas da config, e fluxo OpenSpec
- `messaging-bus`: Telegram envia texto plano sem Markdown, limpa formatação
- `ai-agent-adapter`: Adapter precisa suportar tools (web search) e timeout estendido
- `platform-config`: Personas precisam incluir campos para comando e marcador de conclusão

## Impact

- **engine.py** — refatorar `_agent_conversation` (dois modos), `run_demand_cycle` (fluxo OpenSpec), eliminar hardcoded
- **daemon.py** — gerar comandos `/<agente>` da config, eliminar `AGENT_COMMANDS` hardcoded
- **telegram.py** — remover `parse_mode="Markdown"` de tudo, enviar texto plano
- **config.yaml template** — adicionar campo `command` nas personas
- **agents/po/AGENTS.md** — instruções de marcador `---SPEC_READY---`, formato OpenSpec, busca web
- **agents/dev-orchestrator/AGENTS.md** — instruções de marcador `---DONE---`, execução real, feedback
- **claude_agent_sdk.py** — suporte a tools (web search), timeout configurável por agente
