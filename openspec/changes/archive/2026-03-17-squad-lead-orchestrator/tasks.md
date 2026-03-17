## 1. Formato padrao de AGENTS.md

- [x] 1.1 Definir template padrao de AGENTS.md com secoes: Dominio, Quando Envolver, Responsabilidades, Criterios de Aceite, Marcador de Conclusao, Restricoes, Instrucoes
- [x] 1.2 Reescrever agents/po/AGENTS.md no formato padrao
- [x] 1.3 Reescrever agents/dev-orchestrator/AGENTS.md no formato padrao (renomear para agents/dev/)
- [x] 1.4 Reescrever agents/qa/AGENTS.md no formato padrao
- [x] 1.5 Criar agents/squad-lead/AGENTS.md com instrucoes de coordenacao, lista de tools, e fluxo de decisao

## 2. Config reestruturado

- [x] 2.1 Renomear `personas` para `agents` no PlatformConfig e config.yaml template
- [x] 2.2 Adicionar secao `squad_lead` no config.yaml template (name, avatar)
- [x] 2.3 Criar dataclass SquadLeadConfig no factory.py
- [x] 2.4 Atualizar PlatformConfig.from_yaml para carregar squad_lead + agents
- [x] 2.5 Criar metodo para ler e parsear AGENTS.md de cada agente (extrair secoes padrao)
- [x] 2.6 Atualizar daemon.py para usar `agents` em vez de `personas`

## 3. Tools do Squad Lead

- [x] 3.1 Criar modulo src/orchestrator/tools.py com funcoes: invoke_agent, invoke_parallel, get_status, check_workspace
- [x] 3.2 invoke_agent: recebe nome e prompt, executa _agent_conversation, retorna resultado
- [x] 3.3 invoke_parallel: recebe lista de agentes e prompts, executa via asyncio.gather, retorna lista de resultados
- [x] 3.4 get_status: retorna dict com status de cada agente invocado na demanda atual
- [x] 3.5 check_workspace: executa git status e git log --oneline -5, retorna texto

## 4. Engine como runtime

- [x] 4.1 Remover run_demand_cycle com fluxo fixo PO → Dev → QA
- [x] 4.2 Criar run_squad_lead(demand_id, user_id, text) que inicia Squad Lead com tools
- [x] 4.3 Montar prompt do Squad Lead com: resumo dos agentes disponiveis + AGENTS.md do squad-lead + contexto do projeto
- [x] 4.4 Registrar tools (invoke_agent, invoke_parallel, get_status, check_workspace) no adapter do Squad Lead
- [x] 4.5 Quando agente invocado via tool, injetar AGENTS.md completo do agente no prompt

## 5. Daemon e Telegram

- [x] 5.1 Mensagem sem comando → Squad Lead (nao mais fila de demandas generica)
- [x] 5.2 Gerar comandos de agentes do config.agents (dinamico)
- [x] 5.3 Comando /<agente> → conversa direta com agente (bypass Squad Lead)
- [x] 5.4 Atualizar /help com Squad Lead como padrao + comandos dos agentes

## 6. Execucao paralela

- [x] 6.1 Implementar _run_parallel_agents no engine — asyncio.gather com conversas independentes
- [x] 6.2 Cada agente paralelo tem conversation store independente (demand_id + agent_name)
- [x] 6.3 No Telegram, mensagens paralelas identificadas pelo label do agente
- [x] 6.4 Usuario usa /<comando> para direcionar resposta ao agente especifico durante paralelo

## 7. Testes

- [x] 7.1 Testes para leitura e parse de AGENTS.md (extrair secoes)
- [x] 7.2 Testes para tools (invoke_agent, invoke_parallel, get_status, check_workspace)
- [x] 7.3 Testes para run_squad_lead (Squad Lead invoca agentes via tools)
- [x] 7.4 Testes para execucao paralela (asyncio.gather, conversas independentes)
- [x] 7.5 Testes para config reestruturado (squad_lead + agents)
- [x] 7.6 Testes para daemon (mensagem padrao → Squad Lead, comandos dinamicos)
- [x] 7.7 Verificar cobertura >= 80%
