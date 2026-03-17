## 1. MCP tools de delegacao no adapter

- [x] 1.1 Criar dataclass RunningAgent (agent_name, task, started_at, status, result, demand_id)
- [x] 1.2 Adicionar MCP tool `start_agent(agent_name, task_description)` ao MCP server do adapter — chama callback do engine que inicia agente em background
- [x] 1.3 Adicionar MCP tool `get_running_agents()` ao MCP server — chama callback do engine que retorna estado dos agentes
- [x] 1.4 Adicionar MCP tool `check_artifacts(change_name)` ao MCP server — executa openspec status no workspace e retorna resultado
- [x] 1.5 Registrar callbacks no adapter (set_start_agent_callback, set_get_agents_callback, set_check_artifacts_callback)

## 2. Engine com agentes em background

- [x] 2.1 Adicionar dict _running_agents ao engine para rastrear asyncio tasks
- [x] 2.2 Implementar _start_agent_background(agent_name, prompt, demand_id, user_id) — cria asyncio task, registra em _running_agents, retorna imediatamente
- [x] 2.3 Implementar _on_agent_done callback — atualiza status, salva resultado, notifica usuario, dispara Squad Lead automaticamente
- [x] 2.4 Implementar _get_running_agents_status() — retorna lista com nome, status, tempo, resultado resumido
- [x] 2.5 Implementar _check_artifacts(change_name) — executa openspec status no workspace e retorna resultado formatado

## 3. Squad Lead com chamadas curtas

- [x] 3.1 Refatorar run_squad_lead para usar max_turns=5 em vez de _agent_conversation — chamada SDK unica e curta
- [x] 3.2 Injetar contexto dos agentes em background no prompt do Squad Lead (estado, resultados pendentes)
- [x] 3.3 Implementar _trigger_squad_lead(event_context) — dispara Squad Lead automaticamente quando agente conclui (chamado pelo _on_agent_done)
- [x] 3.4 Reescrever agents/squad-lead/AGENTS.md — instruir a usar tools reais (start_agent, get_running_agents, check_artifacts) em vez de invoke_agent ficticio

## 4. Daemon nao-bloqueante

- [x] 4.1 Refatorar _handle_new_demand para processar mensagens imediatamente sem fila bloqueante
- [x] 4.2 Implementar roteamento: se agente espera input (ask_user pendente) → mensagem vai para agente; senao → Squad Lead
- [x] 4.3 Remover _process_queue sequencial — substituir por processamento imediato por mensagem

## 5. Testes

- [x] 5.1 Testes para start_agent (sucesso, agente inexistente, agente ja rodando)
- [x] 5.2 Testes para get_running_agents (com e sem agentes ativos)
- [x] 5.3 Testes para _on_agent_done (notificacao, disparo do Squad Lead)
- [x] 5.4 Testes para daemon nao-bloqueante (mensagens processadas durante execucao de agente)
- [x] 5.5 Verificar cobertura >= 80%
