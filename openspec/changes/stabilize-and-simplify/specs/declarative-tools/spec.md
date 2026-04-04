## ADDED Requirements

### Requirement: Definição declarativa de MCP tools
O adapter SHALL definir MCP tools como lista de dicts com campos: `name`, `description`, `callback_event`, `params` (dict de nome→tipo). O registro SHALL ser feito via loop sobre essa lista.

#### Scenario: Tool registrada via definição declarativa
- **WHEN** o adapter inicializa o MCP server
- **AND** a lista de tools contém `{"name": "report_progress", "callback_event": "progress", "params": {"agent_name": "str", "message": "str"}}`
- **THEN** o MCP server expõe a tool "report_progress" com os parâmetros definidos

#### Scenario: Nova tool adicionada sem boilerplate
- **WHEN** um desenvolvedor precisa adicionar uma nova MCP tool
- **THEN** basta adicionar um dict à lista de definições (1 entrada, não 1 função)

### Requirement: Handler genérico para tools
O sistema SHALL usar um único handler genérico que extrai parâmetros e invoca `emit(callback_event, **params)`. Handlers individuais por tool SHALL NOT existir.

#### Scenario: Handler genérico despacha corretamente
- **WHEN** a tool "start_agent" é invocada com `{"name": "dev", "task": "implementar feature"}`
- **THEN** o handler genérico chama `emit("start_agent", name="dev", task="implementar feature")`
