# ai-agent-adapter

## Purpose

Interface abstrata para execução de agentes IA, desacoplando o orquestrador de providers específicos (Claude Code, Gemini, Copilot). Permite troca de provider sem alteração de código.

## Requirements

### Requirement: Interface ABC do adapter de IA
O sistema SHALL definir uma classe abstrata `AIAgentAdapter` com os métodos: `run(prompt: str, context: dict) -> str`, `ask(question: str) -> str`, `status() -> AgentStatus`, `on_human_needed(callback: Callable)`. Nenhum componente externo ao adapter SHALL importar implementações concretas.

#### Scenario: Execução de agente via interface
- **WHEN** o orquestrador chama `adapter.run(prompt, context)`
- **THEN** o adapter executa o agente com o provider configurado e retorna o resultado como string

#### Scenario: Status do agente
- **WHEN** o orquestrador chama `adapter.status()`
- **THEN** retorna o estado atual do agente (idle, running, waiting_human, error, done)

### Requirement: Implementação Claude Code
O sistema SHALL fornecer `ClaudeCodeAdapter` que invoca o Claude Code CLI via subprocess com flag `--print`. O adapter SHALL funcionar com a assinatura Claude Code existente do usuário, sem exigir API key separada.

#### Scenario: Execução via CLI subprocess
- **WHEN** `ClaudeCodeAdapter.run(prompt, context)` é chamado
- **THEN** o adapter executa `claude --print` com o prompt via subprocess e retorna o output

#### Scenario: Funcionamento sem API key
- **WHEN** o adapter Claude Code é instanciado
- **THEN** ele usa a autenticação existente do CLI sem exigir configuração adicional de API key

### Requirement: Callback para intervenção humana
O adapter SHALL suportar registro de callback via `on_human_needed` que é invocado quando o agente precisa de decisão humana. O adapter SHALL NOT interagir diretamente com barramento de mensageria.

#### Scenario: Agente precisa de aprovação
- **WHEN** o agente em execução emite um pedido de aprovação
- **THEN** o callback registrado via `on_human_needed` é invocado com a pergunta

### Requirement: Seleção de adapter via configuração
O sistema SHALL selecionar o adapter de IA baseado no campo `ai_provider` do `platform.yaml`. Adicionar novo provider SHALL exigir apenas: novo arquivo de implementação + entrada no platform.yaml.

#### Scenario: Troca de Claude Code para Gemini
- **WHEN** `platform.yaml` tem `ai_provider: gemini`
- **THEN** o sistema instancia `GeminiAdapter` sem alteração em nenhum outro componente
