## ADDED Requirements

### Requirement: Catálogo mínimo de memória no prompt
O sistema SHALL injetar um catálogo compacto (~300 tokens) no prompt do Squad Lead listando: quantidade de lições e temas disponíveis, demandas ativas no journal, e dias de notas disponíveis. O catálogo SHALL incluir instrução de uso das tools de consulta.

#### Scenario: Catálogo com lições disponíveis
- **WHEN** existem 8 lições nos temas "deploy, banco, API, auth"
- **THEN** o prompt inclui "Lições disponíveis (8): deploy, banco, API, auth. Use query_lessons(tema) para detalhes."

#### Scenario: Catálogo sem lições
- **WHEN** o LessonsStore está vazio
- **THEN** a seção de lições é omitida do catálogo

#### Scenario: Catálogo com journal ativo
- **WHEN** existem demandas ativas #42 e #43
- **THEN** o prompt inclui "Journal ativo: demandas #42, #43. Use query_journal(id) para decisões."

### Requirement: MCP tool query_lessons
O sistema SHALL expor uma MCP tool `query_lessons(tema: str, limit: int = 5)` que executa busca FTS5 no LessonsStore e retorna lições formatadas. A tool SHALL ser acessível ao Squad Lead e aos agentes.

#### Scenario: Consulta com resultados
- **WHEN** Squad Lead invoca `query_lessons("deploy")` e existem 3 lições sobre deploy
- **THEN** a tool retorna as 3 lições formatadas com categoria, problema e solução

#### Scenario: Consulta sem resultados
- **WHEN** Squad Lead invoca `query_lessons("tema inexistente")`
- **THEN** a tool retorna mensagem indicando que não há lições sobre o tema

#### Scenario: Limite de resultados
- **WHEN** Squad Lead invoca `query_lessons("banco", limit=2)` e existem 5 lições
- **THEN** a tool retorna apenas as 2 lições mais relevantes

### Requirement: MCP tool query_journal
O sistema SHALL expor uma MCP tool `query_journal(demand_id: str | None = None)` que retorna decisões do journal. Se `demand_id` é fornecido, retorna apenas decisões daquela demanda. Se None, retorna resumo de todas as demandas ativas.

#### Scenario: Consulta de demanda específica
- **WHEN** Squad Lead invoca `query_journal("42")`
- **THEN** a tool retorna todas as decisões registradas para a demanda #42

#### Scenario: Consulta geral
- **WHEN** Squad Lead invoca `query_journal()` com 2 demandas ativas
- **THEN** a tool retorna resumo compacto de decisões de ambas as demandas

### Requirement: MCP tool query_daily_notes
O sistema SHALL expor uma MCP tool `query_daily_notes(days: int = 3)` que retorna notas diárias dos últimos N dias formatadas.

#### Scenario: Consulta de notas recentes
- **WHEN** Squad Lead invoca `query_daily_notes(3)` e existem notas dos últimos 3 dias
- **THEN** a tool retorna notas formatadas dos 3 dias mais recentes

#### Scenario: Sem notas disponíveis
- **WHEN** Squad Lead invoca `query_daily_notes()` e não existem notas
- **THEN** a tool retorna mensagem indicando que não há notas disponíveis
