## Context

O AI Squad possui dois adapters de IA: `ClaudeAgentSDKAdapter` (Claude Agent SDK) e `AgnoAdapter` (framework Agno). Ambos implementam `AIAgentAdapter` e compartilham `SquadMCPToolsServer` para tools de orquestração e `build_prompt()` para montagem de prompts.

O Copilot SDK (`github-copilot-sdk`) é um SDK em technical preview que expõe o engine do GitHub Copilot CLI como API programática. Suporta Python, sessions persistentes, custom tools via `@define_tool`, e MCP servers nativos. A empresa já paga licença Copilot — o adapter usa essa subscription.

## Goals / Non-Goals

**Goals:**
- Implementar adapter Copilot com paridade funcional ao AgnoAdapter
- Reutilizar `SquadMCPToolsServer` via MCP stdio para as 11 tools de orquestração
- Suportar sessions persistentes via `session_id` nativo do SDK
- Autenticação via subscription da org (`GITHUB_TOKEN` ou `copilot auth login`)
- Model routing (fast/powerful) via parâmetro `model` na session
- Dependência opcional (extras group `copilot`)

**Non-Goals:**
- BYOK (Bring Your Own Key) — empresa paga licença, não faz sentido expor API keys
- Subagentes nativos (Copilot SDK não suporta — usar `start_agent` tool via MCP)
- Suporte a streaming de progresso no Telegram (manter `send_and_wait` síncrono)
- Migração de times existentes — é uma opção nova, não substituição

## Decisions

### 1. Tools via MCP server stdio (não @define_tool)

**Escolha:** Usar `mcp_servers` do Copilot SDK apontando para `mcp_tools_server.py` via stdio.

**Alternativa descartada:** Converter definições do `SquadMCPToolsServer` para `@define_tool` do Copilot SDK (padrão que o Agno usa com function generation dinâmica).

**Racional:** O Copilot SDK suporta MCP nativamente como cidadão de primeira classe. O `mcp_tools_server.py` já implementa um servidor MCP stdio completo com JSON-RPC. Usar MCP stdio significa zero código novo para tools — qualquer tool adicionada ao server funciona automaticamente em todos os adapters.

### 2. Autenticação: GITHUB_TOKEN ou CLI login

**Escolha:** Prioridade: (1) `GITHUB_TOKEN` no `.env` → passa como `github_token`, (2) fallback para `use_logged_in_user=True` (credenciais do `copilot auth login`).

**Alternativa descartada:** BYOK com `ANTHROPIC_API_KEY` — empresa já paga licença Copilot, expor API key da Anthropic no Copilot SDK é desnecessário e indesejado.

**Racional:** Mesmo padrão do Claude SDK (`CLAUDE_CODE_OAUTH_TOKEN` ou `claude login`). Validação no `validate_required_tokens` verifica `GITHUB_TOKEN` quando provider é `copilot`.

### 3. Client lifecycle gerenciado pelo adapter

**Escolha:** `CopilotClient.start()` no primeiro `run()` (lazy init), `stop()` via método explícito `shutdown()` chamado pelo daemon no teardown.

**Alternativa descartada:** `start()` no `__init__` — problemático porque `__init__` é síncrono e `start()` é async.

**Racional:** Lazy init evita complexidade de async no construtor. O client é criado no `__init__` mas só inicia na primeira execução. O daemon já tem teardown para cleanup.

### 4. Sessions: demand_id como session_id

**Escolha:** Usar `demand_id` do contexto como `session_id` do Copilot SDK. Resume via `client.resume_session(demand_id)`.

**Racional:** Mesmo padrão do Claude SDK (`conversation_id → session_id`). Persistência nativa do SDK — sem necessidade de SQLite externo como no Agno.

### 5. System message via AGENTS.md

**Escolha:** Injetar conteúdo do AGENTS.md como `system_message.content` na criação da session.

**Racional:** O Copilot SDK suporta `system_message` nativamente. Mais limpo que concatenar no prompt (padrão atual).

### 6. Instanciação no daemon: mesmo padrão do Agno

**Escolha:** Import condicional no `daemon.py` via `_create_copilot_adapter()`, com fallback de erro se dependência não instalada.

```
if config.ai_provider == "copilot":
    return self._create_copilot_adapter(kwargs)
elif config.ai_provider == "agno":
    return self._create_agno_adapter(kwargs)
return self._create_claude_adapter(kwargs)
```

## Risks / Trade-offs

- **[SDK em technical preview]** → O Copilot SDK pode ter breaking changes. Mitigação: dependência opcional, pinned version, adapter isolado — se quebrar, troca para Claude SDK sem afetar nada.

- **[MCP server como processo filho]** → O mcp_tools_server.py roda como subprocess do Copilot CLI. Mitigação: timeout configurável no MCP server config, logs de erro adequados. Trade-off aceitável pelo reuso total de código.

- **[Callbacks via stdio]** → Os callbacks do engine (progress, start_agent, etc.) precisam funcionar via processo MCP stdio separado. O `SquadMCPToolsServer` já suporta isso — mas os callbacks precisam ser injetados antes do server iniciar. Mitigação: usar um wrapper script que recebe callbacks via environment ou named pipe.

- **[Latência de auth]** → Primeira execução pode ser mais lenta (auth flow do GitHub). Mitigação: lazy init do client — overhead só na primeira chamada.
