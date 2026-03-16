## 1. Contexto do Produto

- [x] 1.1 Criar módulo `src/orchestrator/context.py` com classe `ProductContextCollector` — lê README.md, tree 2 níveis, e specs/ existentes do workspace
- [x] 1.2 Implementar limite de 4000 caracteres no README com truncamento e indicador "[truncado]"
- [x] 1.3 Implementar leitura de specs anteriores (lista de demandas com títulos dos proposals)
- [x] 1.4 Integrar `ProductContextCollector` no `engine.dispatch_agent` — injetar contexto no dict de context
- [x] 1.5 Ajustar `_build_prompt` nos adapters (ClaudeCodeCLIAdapter e ClaudeAgentSDKAdapter) para incluir seção "## Contexto do Projeto" quando `product_context` está no context dict

## 2. Artefatos SDD no Repositório

- [x] 2.1 Criar diretório `specs/<demand-id>/` no workspace ao iniciar ciclo de demanda
- [x] 2.2 Salvar resultado do PO como `specs/<demand-id>/proposal.md` após aprovação
- [x] 2.3 Salvar resultado do Dev como `specs/<demand-id>/design.md` após aprovação
- [x] 2.4 Ajustar `_agent_conversation` para retornar resultado e salvá-lo no workspace

## 3. Persistência de Conversa

- [x] 3.1 Criar classe `ConversationStore` em `src/orchestrator/conversation.py` — salva/carrega lista de mensagens em JSON com escrita atômica
- [x] 3.2 Definir formato da mensagem: `{"role": "agent"|"user", "agent_name": str, "content": str, "timestamp": str}`
- [x] 3.3 Integrar `ConversationStore` no `_agent_conversation` — salvar cada mensagem trocada
- [x] 3.4 Implementar limite de 20 mensagens no contexto com resumo das anteriores
- [x] 3.5 Ao retomar conversa, carregar histórico e injetar no prompt inicial

## 4. Retomada de Demandas

- [x] 4.1 Estender `StateManager` para salvar checkpoint com resultados parciais (`plano`, `resultado_dev`) junto com o estado
- [x] 4.2 Implementar método `get_pending_demands()` no StateManager — retorna demandas com estado não-terminal
- [x] 4.3 No startup do daemon, chamar `get_pending_demands()` e re-enfileirar cada demanda com flag `resume=True`
- [x] 4.4 Ajustar `run_demand_cycle` para aceitar flag `resume` — pula fases já concluídas usando dados do checkpoint
- [x] 4.5 Notificar usuário via Telegram ao retomar: "Retomando demanda <id> da fase <estado>"
- [x] 4.6 Tratar JSON corrompido no startup — logar erro, notificar, ignorar demanda

## 5. AGENTS.md Customizáveis

- [x] 5.1 Atualizar `agents/po/AGENTS.md` com instruções de exploração do repo (ler README, listar pastas, verificar specs existentes antes de perguntar)
- [x] 5.2 Atualizar `agents/dev-orchestrator/AGENTS.md` com instruções para salvar artefatos em `specs/<demand-id>/`
- [x] 5.3 Atualizar `agents/qa/AGENTS.md` com instruções para validar contra specs geradas

## 6. Testes

- [x] 6.1 Testes para ProductContextCollector (README, tree, specs, truncamento)
- [x] 6.2 Testes para ConversationStore (save, load, limite, escrita atômica)
- [x] 6.3 Testes para checkpoint do StateManager (save, load, get_pending)
- [x] 6.4 Testes para retomada no daemon (re-enfileirar, skip fases, estado corrompido)
- [x] 6.5 Testes para injeção de product_context no build_prompt dos adapters
- [x] 6.6 Verificar cobertura >= 80%
