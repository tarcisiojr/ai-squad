## Why

O AI Squad precisa rodar em ambientes onde não há assinatura Claude Code — especificamente ambientes com Gemini e Copilot CLI disponíveis. Hoje o único adapter de IA é o `ClaudeAgentSDKAdapter`, o que cria vendor lock-in. Precisamos de um provider alternativo que mantenha **todas** as funcionalidades existentes: MCP tools, delegação de agentes, sessions, model routing, web search e code execution.

## What Changes

- Novo adapter `AgnoAdapter` implementando `AIAgentAdapter` usando o framework Agno
- Agno suporta nativamente: MCP tools (3 transportes), Teams com delegação, sessions/memory, multi-model (Gemini, OpenAI, Claude), web search (DuckDuckGo/Tavily), code execution (PythonTools/ShellTools), human-in-the-loop e guardrails
- As 11 MCP tools do AI Squad (start_agent, report_progress, etc.) serão expostas via MCP server stdio consumido pelo Agno via `MCPTools`
- Configuração via `config.yaml` com `ai_provider: agno`
- Suporte a model routing por tier (fast/powerful) usando models nativos do Agno (Gemini, OpenAI, etc.)
- Factory registra `AgnoAdapter` como provider disponível
- Novo campo opcional `tools` no `config.yaml` para habilitar web search e code execution por agente
- Suporte a Skills do Agno (SKILL.md) com fallback para AGENTS.md existentes — zero mudança nos presets atuais

## Capabilities

### New Capabilities
- `agno-adapter`: Implementação do `AIAgentAdapter` usando framework Agno com suporte a MCP tools, sessions, delegação, web search, code execution e multi-model
- `agno-tools-config`: Configuração declarativa de toolkits Agno (web search, code execution, shell) por agente via config.yaml
- `agno-skills`: Carregamento de skills no Agno com fallback AGENTS.md → SKILL.md. Suporta 3 níveis (projeto, agente, globais) e progressive discovery

### Modified Capabilities
- `ai-agent-adapter`: Adicionar callbacks opcionais para web search e code execution; garantir que a interface suporta providers que gerenciam tools internamente
- `platform-config`: Adicionar campo `tools` opcional na configuração de agentes para declarar toolkits extras (web_search, code_execution, shell)

## Impact

- **Código**: Novo arquivo `src/adapters/agno_adapter.py`, modificações em `src/factory.py` para registro
- **Dependências**: Nova dependência `agno` + extras (`agno[google]`, `agno[tools]`)
- **Config**: Novo valor `agno` para `ai_provider`, novo campo opcional `tools` em agents
- **Testes**: Novos testes para `AgnoAdapter` espelhando os do `ClaudeAgentSDKAdapter`
- **Compatibilidade**: Zero breaking changes — `claude-agent-sdk` continua funcionando normalmente
