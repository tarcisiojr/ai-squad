## 1. Dockerfile e Imagem Base

- [x] 1.1 Reescrever Dockerfile com multi-stage: Python 3.11 + Node.js 20 + git + gh CLI + docker CLI + docker-compose
- [x] 1.2 Instalar claude CLI via npm no Dockerfile
- [x] 1.3 Adicionar health check no Dockerfile (arquivo ou endpoint)
- [x] 1.4 Testar build da imagem e verificar que todas as ferramentas estão no PATH

## 2. Estrutura de Diretórios e Templates

- [x] 2.1 Criar módulo `src/cli/` com `__init__.py`
- [x] 2.2 Criar template `config.yaml` padrão (ai_provider, messaging_provider, agent_timeout, personas, repo_path)
- [x] 2.3 Criar template `.env` com placeholders identificáveis (PREENCHA_AQUI_*)
- [x] 2.4 Criar template `docker-compose.yml` com volumes (workspace, docker.sock, state), env vars, restart policy e resource limits
- [x] 2.5 Criar classe `TeamManager` para gerenciar estrutura `~/.ai-dev-team/teams/<nome>/` (create, list, get_path, exists, validate_env)

## 3. CLI com Click

- [x] 3.1 Adicionar dependências click e python-dotenv no pyproject.toml
- [x] 3.2 Registrar entry point `ai-dev-team = src.cli.main:cli` no pyproject.toml
- [x] 3.3 Implementar comando `create <nome> --repo <caminho>` (validação de repo, geração de templates, feedback ao usuário)
- [x] 3.4 Implementar comando `start <nome>` e `start --all` (validação de .env, build da imagem se necessário, docker-compose up -d)
- [x] 3.5 Implementar comando `stop <nome>` e `stop --all` (docker-compose down)
- [x] 3.6 Implementar comando `list` (tabela com nome, repo, status via docker inspect)
- [x] 3.7 Implementar comando `logs <nome>` com opção `--tail` (docker-compose logs -f)
- [x] 3.8 Implementar comando `status <nome>` (lê state/ do time e exibe demandas ativas)
- [x] 3.9 Implementar comando `build` (reconstrói imagem ai-dev-team:latest)

## 4. Daemon Mode

- [x] 4.1 Criar módulo `src/daemon.py` com classe Daemon (init factory, registrar providers, loop asyncio)
- [x] 4.2 Implementar carregamento de config via config.yaml + variáveis de ambiente (.env) com env vars tendo precedência
- [x] 4.3 Implementar loop infinito de escuta Telegram com polling mode (application.run_polling)
- [x] 4.4 Implementar handler de novas demandas: mensagem de texto → cria demanda → inicia ciclo
- [x] 4.5 Implementar fila de demandas (processar uma por vez, enfileirar as demais)
- [x] 4.6 Implementar graceful shutdown via SIGTERM (salvar estado, notificar Telegram, aguardar etapa atual até 30s)
- [x] 4.7 Implementar logging estruturado (timestamp, nível, demand_id, etapa)

## 5. Adaptações em Módulos Existentes

- [x] 5.1 Adaptar PlatformConfig (factory.py) para suportar carregamento de env vars com precedência sobre YAML
- [x] 5.2 Adaptar PlatformConfig para validar configs obrigatórias (tokens não podem ser placeholder)
- [x] 5.3 Adicionar campo repo_path no PlatformConfig com resolução de caminho absoluto
- [x] 5.4 Configurar TelegramMessageBus como provider padrão em daemon mode
- [x] 5.5 Adicionar suporte a polling mode no TelegramMessageBus (run_polling ao invés de webhook)
- [x] 5.6 Implementar recebimento de novas demandas via texto e voz no TelegramMessageBus

## 6. Testes

- [x] 6.1 Testes unitários para TeamManager (create, list, exists, validate_env)
- [x] 6.2 Testes unitários para cada comando CLI (create, start, stop, list, logs, status, build)
- [x] 6.3 Testes para Daemon (init, shutdown, fila de demandas)
- [x] 6.4 Testes para PlatformConfig adaptado (env vars, validação, repo_path)
- [x] 6.5 Testes de integração: create → start → verificar container rodando → stop
- [x] 6.6 Verificar cobertura ≥ 80%

## 7. Documentação e Finalização

- [x] 7.1 Atualizar pyproject.toml com novas dependências e entry point
- [x] 7.2 Atualizar CLAUDE.md com novos comandos de desenvolvimento
- [x] 7.3 Testar fluxo completo: pip install -e . → ai-dev-team create test --repo . → preencher .env → ai-dev-team start test
