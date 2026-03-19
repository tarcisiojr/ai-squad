## Why

Hoje o usuário precisa escolher de uma lista fixa de presets (`dev-openspec`, `infra-monitor`, etc.) ou criar a estrutura manualmente. Muitos casos de uso não se encaixam nos presets existentes, e criar um pipeline do zero exige conhecimento da estrutura interna (AGENTS.md, pipeline.yaml, step files, quality gates). O comando `ai-squad generate` resolve isso: o usuário descreve em linguagem natural o time que quer, e a IA gera toda a estrutura automaticamente via wizard interativo.

## What Changes

- Novo comando CLI `ai-squad generate` com wizard interativo que coleta: descrição do time, provider de IA, token, canal de comunicação, credenciais do canal, knowledge base (s/N) e nome do time
- Geração via IA de `pipeline.yaml`, step files com quality gates, e `AGENTS.md` para cada agente — tudo baseado na descrição fornecida
- Reaproveitamento do token: o mesmo token usado para gerar é salvo no `.env` do time criado
- Suporte a múltiplos providers de geração (Anthropic, Agno, OpenAI) com modelo default por provider
- O comando absorve o `create` — gera a estrutura E cria o time em um único fluxo
- Perguntas dinâmicas do canal: dependendo da escolha (Telegram/GChat/CLI), coleta credenciais específicas

## Capabilities

### New Capabilities
- `cli-generate-wizard`: Wizard interativo no CLI que coleta informações do usuário (descrição, provider, token, canal, knowledge base, nome) e orquestra a geração do time
- `ai-preset-generator`: Motor de geração que usa IA para produzir pipeline.yaml, step files e AGENTS.md a partir de uma descrição em linguagem natural
- `generation-provider`: Abstração de providers de IA para geração (Anthropic, Agno, OpenAI) com modelo default por provider

### Modified Capabilities
- `platform-config`: O `.env` agora é preenchido automaticamente com tokens coletados no wizard, em vez de exigir edição manual

## Impact

- **CLI**: Novo comando `generate` em `src/cli/main.py`
- **Novos módulos**: `src/cli/wizard.py` (interação), `src/cli/generators/` (providers de geração)
- **team_manager.py**: Reutilização da lógica de criação de diretórios e config existente
- **Dependências**: SDK do provider de IA como dependência opcional (anthropic, openai, agno)
- **Templates/prompts**: Prompt de geração que conhece a estrutura de presets para produzir YAML/markdown válidos
