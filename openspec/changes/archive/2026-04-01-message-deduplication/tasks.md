# Tasks: Message Deduplication

## Sequência de Implementação

### Task 1: Adicionar `progress_log` ao RunningAgent
- **Arquivo**: `src/orchestrator/tools.py`
- **O que fazer**: Adicionar campo `progress_log: list[str]` ao dataclass `RunningAgent`
- **Dependências**: nenhuma
- [x] Concluído

### Task 2: Redirecionar `report_progress` para canal interno
- **Arquivo**: `src/orchestrator/engine.py` (método `_handle_progress`)
- **O que fazer**:
  - Armazenar mensagem no `RunningAgent.progress_log` em vez de enviar ao usuário
  - Na primeira chamada de progress, enviar status leve ("⚙️ {label} trabalhando...")
  - Chamadas subsequentes apenas acumulam no log interno
- **Dependências**: Task 1
- [x] Concluído

### Task 3: Remover envio direto no `on_agent_done`
- **Arquivo**: `src/orchestrator/agent_runner.py` (método `on_agent_done`)
- **O que fazer**:
  - Remover `send_message` direto ao usuário (linhas 313-318)
  - Alterar `save_message` de role "assistant" para "internal" (linhas 304-311)
  - Enriquecer contexto do trigger com instrução anti-repetição
- **Dependências**: nenhuma (pode ser paralelo com Task 2)
- [x] Concluído

### Task 4: Incluir progress_log no contexto do Squad Lead
- **Arquivo**: `src/orchestrator/engine.py` (método `_trigger_squad_lead_for_agent`)
- **O que fazer**:
  - Montar contexto com últimos 5 itens do progress_log
  - Passar como parte do event_context ao `run_squad_lead`
- **Dependências**: Task 1, Task 2
- [x] Concluído

### Task 5: Adicionar instrução anti-repetição no prompt do Squad Lead
- **Arquivo**: `src/orchestrator/engine.py` (método `_build_squad_lead_prompt`)
- **O que fazer**:
  - Adicionar bloco de instrução sobre comunicação concisa
  - Instruir separação entre resultado e decisão de próximo passo
  - Instruir a nunca parafrasear o que já foi comunicado
- **Dependências**: nenhuma (pode ser paralelo)
- [x] Concluído

### Task 6: Atualizar descrição da tool `report_progress`
- **Arquivo**: `src/adapters/mcp_tools_server.py`
- **O que fazer**: Atualizar description para refletir que o progresso é interno (Squad Lead recebe e decide o que comunicar)
- **Dependências**: nenhuma
- [x] Concluído

### Task 7: Tratar mensagens "internal" no histórico de conversa
- **Arquivo**: `src/orchestrator/conversation.py`
- **O que fazer**:
  - Garantir que `format_history_for_prompt` inclua mensagens "internal" apenas quando destinadas ao Squad Lead
  - Mensagens "internal" não devem aparecer como "já comunicadas ao usuário"
- **Dependências**: Task 3
- [x] Concluído

### Task 8: Testes
- **Arquivos**: `tests/orchestrator/test_agent_runner.py`, `tests/orchestrator/test_engine.py`
- **O que fazer**:
  - Testar que `on_agent_done` NÃO envia mensagem direto ao usuário
  - Testar que `report_progress` armazena no progress_log
  - Testar que status leve é enviado apenas 1x
  - Testar que Squad Lead recebe progress_log no contexto
- **Dependências**: Tasks 1-7
- [x] Concluído

## Ordem de Execução

```
Task 1 (RunningAgent) ──┐
                        ├──► Task 2 (report_progress) ──┐
Task 3 (on_agent_done) ─┤                               ├──► Task 7 (conversation) ──► Task 8 (testes)
Task 5 (prompt SL) ─────┤                               │
Task 6 (tool desc) ─────┘   Task 4 (progress context) ──┘
```
