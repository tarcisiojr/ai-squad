## Why

O comando `ai-squad generate` permite criar times via IA usando providers anthropic, openai e agno. Porém, o Copilot — que já é um provider suportado para execução de agentes — não está disponível como opção de geração. Usuários que usam GitHub Copilot não conseguem usar o `generate` para criar seus times, sendo obrigados a usar outro provider ou configurar manualmente.

## What Changes

- Criar `CopilotGenerator` implementando `GeneratorProvider` em `src/cli/generators/copilot.py`
- Registrar o provider "copilot" em `PROVIDER_CONFIGS` e `get_provider()` na interface
- Adicionar "copilot" como opção no wizard interativo (`_ask_provider` e `_ask_token`)
- Copilot não exige token manual — autenticação via `copilot auth login` (CLI) ou `GITHUB_TOKEN` env var
- O wizard deve permitir token vazio para copilot (auth via CLI) ou aceitar GITHUB_TOKEN opcional

## Capabilities

### New Capabilities
- `copilot-generator`: Provider de geração de presets via GitHub Copilot SDK, seguindo o padrão GeneratorProvider

### Modified Capabilities
- `generation-provider`: Adicionar copilot ao registro de providers (PROVIDER_CONFIGS, get_provider)
- `cli-generate-wizard`: Adicionar copilot como opção de provider, com fluxo de token adaptado (opcional)

## Impact

- **Código**: `src/cli/generators/` (novo arquivo + interface.py), `src/cli/wizard.py`
- **Dependências**: `copilot-sdk` já é dependência opcional (`pip install -e '.[copilot]'`)
- **Config**: Copilot no generate produz `ai_provider: copilot` no config.yaml do time
- **Autenticação**: Sem breaking change — token continua obrigatório para outros providers
