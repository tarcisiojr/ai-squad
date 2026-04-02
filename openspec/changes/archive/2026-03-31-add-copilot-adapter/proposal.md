## Why

A empresa já paga licença GitHub Copilot para a organização. Atualmente o AI Squad só suporta Claude Agent SDK e Agno como providers de IA. Adicionar suporte ao Copilot SDK permite usar a subscription existente da org para rodar agentes (inclusive com modelos Claude como Sonnet 4.6 via Copilot), reduzindo custos e diversificando providers.

## What Changes

- Novo adapter `CopilotAdapter` em `src/adapters/copilot_adapter.py` implementando `AIAgentAdapter`
- Reutilização do `SquadMCPToolsServer` existente para expor as 11 tools de orquestração via MCP stdio
- Autenticação via subscription da org GitHub (`GITHUB_TOKEN` ou `copilot auth login`)
- Suporte a sessions persistentes com `session_id` + `resume_session` nativo do SDK
- Instanciação condicional no `daemon.py` (mesmo padrão do Agno: import condicional)
- Novo valor `copilot` para `ai_provider` no `config.yaml`
- Validação de token `GITHUB_TOKEN` no `validate_required_tokens`
- Dependência opcional `github-copilot-sdk` (extras: `pip install -e '.[copilot]'`)

## Capabilities

### New Capabilities
- `copilot-adapter`: Implementação do AIAgentAdapter usando GitHub Copilot SDK com suporte a MCP tools, sessions persistentes e autenticação via subscription da org

### Modified Capabilities
- `ai-agent-adapter`: Adicionar requirement para implementação Copilot (novo provider)
- `platform-config`: Adicionar validação de token `GITHUB_TOKEN` para provider `copilot`

## Impact

- **Código**: `src/adapters/copilot_adapter.py` (novo), `src/daemon.py` (novo método `_create_copilot_adapter`), `src/factory.py` (validação de token)
- **Dependências**: `github-copilot-sdk` como dependência opcional (extras group `copilot`)
- **Config**: Novo valor `copilot` aceito em `ai_provider`
- **Auth**: Requer `GITHUB_TOKEN` no `.env` ou login prévio via `copilot auth login`
- **Infra**: Copilot CLI deve estar instalado no ambiente (SDK embute binário via wheel)
