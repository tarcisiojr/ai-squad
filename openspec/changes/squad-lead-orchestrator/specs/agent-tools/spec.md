## ADDED Requirements

### Requirement: Tool invoke_agent
O Squad Lead SHALL ter uma tool para invocar um agente especifico.

#### Scenario: Invocar agente existente
- **WHEN** o Squad Lead chama invoke_agent("po", "Especificar login")
- **THEN** o engine MUST iniciar conversa do PO com o usuario, aguardar conclusao, e retornar o resultado ao Squad Lead

#### Scenario: Invocar agente inexistente
- **WHEN** o Squad Lead chama invoke_agent com nome de agente que nao existe no config
- **THEN** a tool MUST retornar erro informando agentes disponiveis

### Requirement: Tool invoke_parallel
O Squad Lead SHALL ter uma tool para invocar multiplos agentes em paralelo.

#### Scenario: Invocar dois agentes em paralelo
- **WHEN** o Squad Lead chama invoke_parallel(["dev-frontend", "dev-backend"], ["prompt1", "prompt2"])
- **THEN** o engine MUST executar ambos simultaneamente via asyncio.gather e retornar resultados de todos

#### Scenario: Usuario direciona resposta durante paralelo
- **WHEN** multiplos agentes estao conversando em paralelo
- **THEN** o usuario MUST usar /<comando> para direcionar sua resposta ao agente especifico

### Requirement: Tool get_status
O Squad Lead SHALL ter uma tool para verificar o andamento da demanda.

#### Scenario: Status da demanda
- **WHEN** o Squad Lead chama get_status()
- **THEN** MUST retornar lista de agentes invocados, seus status (concluido/em andamento/pendente) e resumo dos resultados

### Requirement: Tool check_workspace
O Squad Lead SHALL ter uma tool para verificar mudancas no workspace.

#### Scenario: Verificar mudancas apos Dev
- **WHEN** o Squad Lead chama check_workspace()
- **THEN** MUST retornar saida de git status e git log dos ultimos commits
