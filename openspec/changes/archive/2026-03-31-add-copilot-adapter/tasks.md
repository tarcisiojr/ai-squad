## 1. Dependência e configuração

- [x] 1.1 Adicionar `github-copilot-sdk` como dependência opcional no `pyproject.toml` (extras group `copilot`)
- [x] 1.2 Adicionar validação de `GITHUB_TOKEN` no `validate_required_tokens` do `factory.py` para provider `copilot`
- [x] 1.3 Atualizar template de `.env` no CLI para incluir `GITHUB_TOKEN` quando provider é `copilot`

## 2. Implementação do CopilotAdapter

- [x] 2.1 Criar `src/adapters/copilot_adapter.py` com classe `CopilotAdapter` herdando `AIAgentAdapter`
- [x] 2.2 Implementar `__init__` com: CopilotClient (lazy), SquadMCPToolsServer, sessions dict, configuração de auth (GITHUB_TOKEN ou use_logged_in_user)
- [x] 2.3 Implementar `_ensure_client_started()` para lazy init assíncrono do CopilotClient
- [x] 2.4 Implementar `_get_or_create_session()` com create_session (model, session_id, system_message, mcp_servers, on_permission_request) e resume_session
- [x] 2.5 Implementar `run(prompt, context)` com: build_prompt, model_override, session management, send_and_wait, extração de response.data.content
- [x] 2.6 Implementar retry com backoff exponencial (2/4/8s) — mesmo padrão do AgnoAdapter
- [x] 2.7 Implementar delegação de callbacks para SquadMCPToolsServer (set_progress_callback, set_start_agent_callback, etc.)
- [x] 2.8 Implementar `ask()`, `status()`, `on_human_needed()`, `shutdown()`

## 3. Integração no daemon

- [x] 3.1 Adicionar `_create_copilot_adapter()` no `daemon.py` com import condicional e mensagem de erro se dependência ausente
- [x] 3.2 Adicionar branch `elif config.ai_provider == "copilot"` na seleção de adapter
- [x] 3.3 Adicionar chamada a `adapter.shutdown()` no teardown do daemon (se adapter tem método shutdown)

## 4. Testes

- [x] 4.1 Criar `tests/test_copilot_adapter.py` com testes unitários: init, run, ask, status, callbacks, retry, session management
- [x] 4.2 Testar auth: GITHUB_TOKEN presente vs ausente (fallback para use_logged_in_user)
- [x] 4.3 Testar model_override: session criada com modelo correto
- [x] 4.4 Testar integração com SquadMCPToolsServer: callbacks delegados corretamente
- [x] 4.5 Testar validate_required_tokens para provider copilot
- [x] 4.6 Testar _create_copilot_adapter no daemon com e sem dependência instalada
