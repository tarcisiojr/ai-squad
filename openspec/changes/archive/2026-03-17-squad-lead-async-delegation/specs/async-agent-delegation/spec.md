## ADDED Requirements

### Requirement: Squad Lead delega agentes via MCP tool start_agent
O engine SHALL expor uma MCP tool `start_agent` que inicia um agente em background e retorna imediatamente.

#### Scenario: Squad Lead inicia PO em background
- **WHEN** o Squad Lead chama `start_agent("po", "Especificar demanda: criar site")`
- **THEN** o engine MUST iniciar o PO como asyncio task em background e retornar resposta imediata "Agente po iniciado"

#### Scenario: start_agent com agente inexistente
- **WHEN** o Squad Lead chama `start_agent("agente-fake", "...")`
- **THEN** a tool MUST retornar erro com lista de agentes disponiveis

#### Scenario: start_agent com agente ja rodando
- **WHEN** o Squad Lead chama `start_agent("po", "...")` e o PO ja esta em execucao
- **THEN** a tool MUST retornar erro informando que o agente ja esta rodando

### Requirement: Squad Lead consulta status dos agentes via MCP tool get_running_agents
O engine SHALL expor uma MCP tool `get_running_agents` que retorna o estado de todos os agentes.

#### Scenario: Consulta com agentes rodando
- **WHEN** o Squad Lead chama `get_running_agents()`
- **THEN** a tool MUST retornar lista com nome, status (running/done/error), tempo decorrido e resultado (se concluido)

#### Scenario: Consulta sem agentes ativos
- **WHEN** o Squad Lead chama `get_running_agents()` e nenhum agente esta rodando
- **THEN** a tool MUST retornar lista vazia

### Requirement: Squad Lead verifica artefatos via MCP tool check_artifacts
O engine SHALL expor uma MCP tool `check_artifacts` que verifica o estado dos artefatos openspec.

#### Scenario: Verificacao de artefatos completos
- **WHEN** o Squad Lead chama `check_artifacts("minha-demanda")`
- **THEN** a tool MUST retornar quais artefatos existem (proposal, specs, design, tasks) e se estao completos

### Requirement: Notificacao automatica ao concluir agente
O engine SHALL notificar o usuario e disparar o Squad Lead quando um agente background conclui.

#### Scenario: PO conclui em background
- **WHEN** o PO termina sua execucao em background
- **THEN** o engine MUST enviar notificacao ao usuario e disparar chamada ao Squad Lead com contexto do resultado

#### Scenario: Agente falha em background
- **WHEN** um agente em background lanca excecao
- **THEN** o engine MUST notificar o usuario sobre o erro e registrar o estado como error
