## 1. Setup do Projeto

- [x] 1.1 Criar estrutura de diretórios do projeto (src/, tests/, agents/, specs/, state/)
- [x] 1.2 Configurar pyproject.toml com dependências (python-telegram-bot, openai, pyyaml, pytest, pytest-cov, pytest-asyncio)
- [x] 1.3 Criar platform.yaml com configuração base (ai_provider: claude-code, messaging_provider: cli)
- [x] 1.4 Configurar pytest com cobertura mínima de 80%

## 2. Interfaces ABC (Contratos)

- [x] 2.1 Implementar ABC `MessageBus` em src/barramento/interface.py com métodos: send_message, send_approval_request, receive_message, receive_voice, notify
- [x] 2.2 Implementar ABC `AIAgentAdapter` em src/adapters/interface.py com métodos: run, ask, status, on_human_needed
- [x] 2.3 Definir enum `AgentStatus` (idle, running, waiting_human, error, done) e enum `DemandState` (idle, po_working, awaiting_plan_approval, dev_working, awaiting_pr_approval, ci_running, qa_validating, done)
- [x] 2.4 Escrever testes unitários para validação das interfaces e enums

## 3. Configuração e Factory

- [x] 3.1 Implementar carregamento e validação de platform.yaml em src/factory.py (PlatformConfig dataclass)
- [x] 3.2 Implementar PlatformFactory com mapeamento provider → implementação e instanciação via construtor
- [x] 3.3 Escrever testes para carregamento de configuração válida e inválida
- [x] 3.4 Escrever testes para factory com providers registrados e não registrados

## 4. Barramento de Mensageria

- [x] 4.1 Implementar CLIMessageBus em src/barramento/cli.py (stdin/stdout para testes locais)
- [x] 4.2 Escrever testes para CLIMessageBus (send_message, send_approval_request, receive_message)
- [x] 4.3 Implementar TelegramMessageBus em src/barramento/telegram.py (python-telegram-bot)
- [x] 4.4 Implementar transcrição de voz via Whisper API no TelegramMessageBus
- [x] 4.5 Implementar suporte a identidade por persona (token, nome, avatar separados)
- [x] 4.6 Escrever testes para TelegramMessageBus com mocks de API

## 5. AI Agent Adapter

- [x] 5.1 Implementar ClaudeCodeAdapter em src/adapters/claude_code.py (subprocess com `claude --print`)
- [x] 5.2 Implementar callback on_human_needed e roteamento de pedidos de aprovação
- [x] 5.3 Implementar timeout configurável e tratamento de erros do subprocess
- [x] 5.4 Escrever testes para ClaudeCodeAdapter com mock de subprocess

## 6. Agent Registry

- [x] 6.1 Definir schema do registry.yaml (nome, domínio, protocolo, ferramentas, versão, adapter)
- [x] 6.2 Implementar AgentRegistry em src/registry/registry.py com carregamento do YAML e matching por domínio
- [x] 6.3 Criar estrutura de agentes base: agents/po/, agents/dev-orchestrator/, agents/qa/ com AGENTS.md e symlinks
- [x] 6.4 Criar subagente agents/dev-web/ com AGENTS.md, skills/, tools.yaml e symlinks
- [x] 6.5 Escrever testes para matching de agente por domínio e extensibilidade

## 7. Orquestrador de Estado

- [x] 7.1 Implementar máquina de estados em src/orchestrator/engine.py com transições válidas e rejeição de inválidas
- [x] 7.2 Implementar persistência JSON em src/orchestrator/state.py com escrita atômica (temp + rename)
- [x] 7.3 Implementar despacho de agentes via AIAgentAdapter injetado no construtor
- [x] 7.4 Implementar roteamento de decisões humanas (ask → MessageBus.send_approval_request)
- [x] 7.5 Implementar gerenciamento de worktrees git por subagente
- [x] 7.6 Escrever testes para máquina de estados (transições válidas e inválidas)
- [x] 7.7 Escrever testes para persistência e recuperação de estado
- [x] 7.8 Escrever testes para roteamento de decisões humanas

## 8. Contratos e Specs do Projeto

- [x] 8.1 Criar estrutura specs/ com diretório para submodulos git
- [x] 8.2 Criar template de AGENTS.md para submodulos com seções padrão
- [x] 8.3 Documentar workflow de criação de contratos (OpenAPI, AsyncAPI, schemas)

## 9. Integração e Testes E2E

- [x] 9.1 Criar teste de integração: fluxo completo com CLIMessageBus + mock adapter (idle → done)
- [x] 9.2 Criar teste de integração: troca de provider via platform.yaml
- [x] 9.3 Validar cobertura de testes ≥ 80%
- [x] 9.4 Validar que nenhum componente importa implementação concreta diretamente

## 10. Docker e Isolamento

- [x] 10.1 Criar Dockerfile base para execução de agentes
- [x] 10.2 Criar devcontainer.json com ambiente de desenvolvimento
- [x] 10.3 Integrar execução de agentes via Docker no orquestrador
- [x] 10.4 Escrever testes de isolamento (agente não acessa filesystem do host)
