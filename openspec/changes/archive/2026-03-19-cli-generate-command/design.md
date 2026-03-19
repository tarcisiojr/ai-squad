## Context

Hoje o CLI oferece `ai-squad create --preset <nome>` com presets fixos (dev-openspec, infra-monitor, etc.). O usuário que não encontra um preset adequado precisa criar manualmente pipeline.yaml, step files e AGENTS.md — estruturas complexas que exigem conhecimento interno do sistema.

O comando `generate` usa IA para gerar toda essa estrutura a partir de uma descrição em linguagem natural, via wizard interativo no terminal. O mesmo token informado para geração é reaproveitado no `.env` do time criado.

## Goals / Non-Goals

**Goals:**
- Wizard interativo que coleta informações e gera preset completo via IA
- Suporte a múltiplos providers de geração (Anthropic, Agno, OpenAI) com defaults sensatos
- Reaproveitamento do token: usado para gerar e salvo no `.env`
- Perguntas condicionais baseadas nas escolhas do usuário (canal → credenciais específicas)
- Geração de pipeline.yaml, step files e AGENTS.md válidos e prontos para uso

**Non-Goals:**
- Salvar preset gerado como template reutilizável (pode copiar manualmente)
- Cascata de resolução de token (env var, credentials file) — só prompt interativo
- Validação semântica do output da IA (confiamos na geração, usuário ajusta depois)
- Suporte a modo Docker no generate (apenas modo local por enquanto)

## Decisions

### 1. Wizard interativo com Click prompts

**Decisão:** Usar `click.prompt()` e `click.Choice` nativos do Click (já é dependência do projeto).

**Alternativa considerada:** Biblioteca rica tipo `questionary` ou `inquirer` — descartada para não adicionar dependência.

**Fluxo de perguntas:**
1. Descrição do time (texto livre)
2. Provider de IA (choice: anthropic/agno/openai, default: anthropic)
3. Token do provider (prompt com `hide_input=True`)
4. Canal de comunicação (choice: telegram/gchat/cli, default: telegram)
5. Credenciais do canal (condicionais — ex: bot token + chat id para Telegram)
6. Knowledge base (confirm, default: não)
7. Nome do time (texto)

### 2. Geração via chamada direta à API do provider

**Decisão:** Chamar a API do provider escolhido diretamente (anthropic SDK, openai SDK, ou agno SDK) com um prompt estruturado que descreve o formato esperado de output.

**Alternativa considerada:** Usar o próprio `AIAgentAdapter` do sistema — descartado porque o adapter é complexo (MCP tools, callbacks) e aqui só precisamos de uma chamada simples de completions.

**Modelo default por provider:**
- Anthropic: `claude-haiku-4-5-20251001` (rápido e barato para gerar config)
- OpenAI: `gpt-4o-mini`
- Agno: modelo default do provider

### 3. Prompt de geração com exemplos de presets existentes

**Decisão:** O prompt para a IA inclui a estrutura de um preset existente (dev-openspec) como exemplo, mais as regras de formato (pipeline.yaml schema, AGENTS.md structure, step file format).

**Formato de output:** JSON estruturado com campos para pipeline, agents e steps — parseado em código para gerar os arquivos.

### 4. Módulo `src/cli/generators/` com interface base

**Decisão:** Criar `GeneratorProvider` (ABC) com método `generate(prompt) → str`, e implementações por provider (anthropic, openai, agno).

```
src/cli/generators/
├── __init__.py
├── interface.py       # ABC GeneratorProvider
├── anthropic.py       # AnthropicGenerator
├── openai.py          # OpenAIGenerator
└── agno.py            # AgnoGenerator
```

**Justificativa:** Segue o mesmo padrão de desacoplamento via ABC já usado em `adapters/` e `messaging/`.

### 5. Reaproveitamento do token no .env

**Decisão:** O token coletado no wizard é usado para duas coisas:
1. Instanciar o GeneratorProvider e fazer a chamada de geração
2. Escrito no `.env` gerado como valor da variável correspondente (ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.)

As credenciais do canal (bot token, chat id) também são escritas diretamente no `.env`.

### 6. Integração com TeamManager existente

**Decisão:** Após a IA gerar a estrutura, o comando `generate` NÃO chama `TeamManager.create_local()` (que copia de preset). Em vez disso, cria os diretórios e arquivos diretamente, reutilizando apenas a lógica de:
- Criação de `state/`
- Geração de `.env` (com valores reais, não placeholders)
- Estrutura de diretórios (`agents/`, `pipeline/steps/`)

### 7. Mapeamento provider de geração → provider do time

**Decisão:** O provider escolhido para geração é o mesmo usado para rodar o time. Mapeamento:
- anthropic → `ai_provider: claude-agent-sdk`, env var: `CLAUDE_CODE_OAUTH_TOKEN`
- agno → `ai_provider: agno`, env var: `GOOGLE_API_KEY`
- openai → `ai_provider: openai`, env var: `OPENAI_API_KEY`

## Risks / Trade-offs

- **[Qualidade da geração]** A IA pode gerar pipeline/agents que não seguem perfeitamente o formato esperado → Mitigação: prompt com exemplos concretos + validação básica de schema do YAML gerado
- **[SDKs opcionais]** Importar anthropic/openai/agno no CLI adiciona dependências → Mitigação: import lazy (só importa o SDK do provider escolhido), com mensagem clara se não instalado
- **[Token exposto no terminal]** `hide_input=True` do Click não ecoa, mas o token fica em memória → Risco aceitável, mesmo comportamento de qualquer CLI que pede credenciais
- **[Modo local apenas]** Não suporta Docker no generate inicial → Trade-off consciente, simplicidade primeiro
