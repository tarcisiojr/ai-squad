## Why

O Squad Lead hoje executa numa unica chamada SDK longa (max_turns=30) que bloqueia todo o sistema. Enquanto ele processa, o usuario nao consegue interagir — perguntas ficam na fila ou sao engolidas pelo ask_user. As tools de invocacao de agentes (invoke_agent, invoke_parallel) existem apenas como texto no AGENTS.md, nao sao tools reais do SDK. O Squad Lead fica girando sem conseguir delegar de verdade, ate dar timeout.

## What Changes

- **Squad Lead com chamadas SDK curtas** — cada mensagem do usuario gera UMA chamada ao Squad Lead com max_turns baixo (3-5), ele responde rapido e delega
- **MCP tools reais para delegacao** — start_agent, get_running_agents, check_artifacts como tools MCP que o Squad Lead pode chamar durante a execucao
- **Agentes rodam em background** — PO, Dev, QA executam como asyncio tasks separadas, sem bloquear o loop principal
- **Mensagens do usuario nunca bloqueiam** — daemon processa mensagens imediatamente, sem fila sequencial bloqueante
- **Notificacao automatica ao concluir** — quando um agente background termina, engine notifica usuario e dispara Squad Lead para proximo passo
- **Remoção do _agent_conversation para Squad Lead** — Squad Lead nao usa mais o loop de conversa bidirecional, usa chamadas diretas ao SDK

## Capabilities

### New Capabilities
- `async-agent-delegation`: MCP tools para o Squad Lead delegar trabalho a agentes em background (start_agent, get_running_agents, check_artifacts) e receber resultados via callbacks
- `non-blocking-messaging`: Daemon processa mensagens do usuario imediatamente sem bloquear, mesmo com agentes rodando em background

### Modified Capabilities
- `orchestrator`: Engine gerencia agentes em background via asyncio tasks, com tracking de estado e notificacao automatica ao concluir
- `execution-feedback`: Feedback de progresso integrado com agentes em background — report_progress dos agentes e notificacoes automaticas de conclusao

## Impact

- **src/orchestrator/engine.py** — refatorar para gerenciar _running_agents como asyncio tasks, adicionar metodos start_agent_background, get_running_agents_status; Squad Lead usa chamadas SDK curtas
- **src/adapters/claude_agent_sdk.py** — adicionar MCP tools reais (start_agent, get_running_agents, check_artifacts) ao MCP server
- **src/daemon.py** — remover processamento sequencial bloqueante; mensagens sempre processadas imediatamente
- **agents/squad-lead/AGENTS.md** — reescrever para usar tools reais de delegacao em vez de invoke_agent ficticio
