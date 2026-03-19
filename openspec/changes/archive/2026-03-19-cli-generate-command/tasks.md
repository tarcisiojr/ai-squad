## Tasks

### 1. Interface GeneratorProvider
- [x] Criar `src/cli/generators/__init__.py`
- [x] Criar `src/cli/generators/interface.py` com ABC `GeneratorProvider` (método `generate(prompt: str) → str`)
- [x] Definir mapeamento de provider → ai_provider, env_var e modelo default

### 2. Implementação dos providers de geração
- [x] Criar `src/cli/generators/anthropic.py` — `AnthropicGenerator` usando SDK anthropic com modelo `claude-haiku-4-5-20251001`
- [x] Criar `src/cli/generators/openai.py` — `OpenAIGenerator` usando SDK openai com modelo `gpt-4o-mini`
- [x] Criar `src/cli/generators/agno.py` — `AgnoGenerator` usando SDK agno
- [x] Tratamento de ImportError com mensagem clara para SDK não instalado em cada provider

### 3. Prompt de geração
- [x] Criar `src/cli/generators/prompt.py` com template de prompt que inclui: descrição do usuário, formato JSON esperado de output, e exemplo de preset real (dev-openspec) como referência
- [x] O prompt DEVE instruir a IA a gerar: pipeline (name, description, steps), agents (nome, AGENTS.md content) e step files (quality gates, veto conditions)

### 4. Wizard interativo
- [x] Criar `src/cli/wizard.py` com classe `GenerateWizard` que encapsula o fluxo de perguntas
- [x] Implementar coleta de descrição do time (texto livre, obrigatório)
- [x] Implementar seleção de provider (click.Choice: anthropic/agno/openai, default: anthropic)
- [x] Implementar coleta de token (click.prompt com hide_input=True, obrigatório)
- [x] Implementar seleção de canal (click.Choice: telegram/gchat/cli, default: telegram)
- [x] Implementar coleta condicional de credenciais do canal (Telegram: bot_token + chat_id; CLI: nada)
- [x] Implementar pergunta de knowledge base (click.confirm, default: False)
- [x] Implementar coleta do nome do time (texto, obrigatório)

### 5. Geração e criação da estrutura
- [x] Implementar parsing do JSON retornado pela IA para extrair pipeline, agents e steps
- [x] Implementar criação dos diretórios: `.ai-squad/`, `state/`, `agents/<nome>/`, `pipeline/steps/`
- [x] Implementar escrita do `pipeline/pipeline.yaml` a partir do output da IA
- [x] Implementar escrita dos step files `.md` em `pipeline/steps/`
- [x] Implementar escrita dos `AGENTS.md` por agente (incluindo squad-lead)
- [x] Implementar geração do `config.yaml` com agents, ai_provider, messaging_provider e knowledge (se habilitado)
- [x] Implementar geração do `.env` com token real e credenciais do canal (sem placeholders)
- [x] Criar diretório `knowledge/` se knowledge base habilitado

### 6. Comando CLI generate
- [x] Adicionar comando `generate` ao grupo `cli` em `src/cli/main.py`
- [x] Integrar wizard → provider → geração → criação de estrutura
- [x] Exibir resumo final (agentes, steps, checkpoints) e comando `ai-squad start <nome>`
- [x] Tratar erro de time já existente (`.ai-squad/` já presente)

### 7. Testes
- [x] Testes unitários para `GenerateWizard` (mock de click.prompt)
- [x] Testes unitários para cada `GeneratorProvider` (mock de SDK)
- [x] Testes unitários para parsing do JSON de geração
- [x] Testes unitários para criação da estrutura de diretórios
- [x] Teste de integração do comando `generate` (click.testing.CliRunner)
