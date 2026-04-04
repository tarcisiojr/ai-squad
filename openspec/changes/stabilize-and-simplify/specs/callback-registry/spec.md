## ADDED Requirements

### Requirement: Registry de callbacks via dict
O adapter SHALL usar um `dict[str, Callable]` para registrar callbacks. O método `on(event, callback)` SHALL registrar um callback e `emit(event, *args, **kwargs)` SHALL invocar o callback registrado. Eventos sem callback registrado SHALL ser no-op.

#### Scenario: Callback registrado e invocado
- **WHEN** `adapter.on("progress", my_handler)` é chamado
- **AND** `adapter.emit("progress", "agent1", "mensagem")` é executado
- **THEN** `my_handler("agent1", "mensagem")` é invocado

#### Scenario: Evento sem callback é no-op
- **WHEN** `adapter.emit("unknown_event", data)` é executado
- **AND** nenhum callback foi registrado para "unknown_event"
- **THEN** nenhum erro é levantado e a execução continua

### Requirement: Constantes tipadas para eventos
O sistema SHALL definir constantes para nomes de eventos (ex: `EVENT_PROGRESS = "progress"`, `EVENT_START_AGENT = "start_agent"`). Todos os usos de `on()` e `emit()` SHALL usar essas constantes.

#### Scenario: Uso de constante em vez de string literal
- **WHEN** o engine registra callbacks no adapter
- **THEN** usa `adapter.on(EVENT_PROGRESS, handler)` em vez de `adapter.on("progress", handler)`

### Requirement: Eliminação de setters individuais
Os métodos `set_progress_callback()`, `set_start_agent_callback()` e os demais 9 setters individuais SHALL ser removidos. A interface `AIAgentAdapter` SHALL expor apenas `on(event, callback)` e `emit(event, *args)`.

#### Scenario: Interface simplificada
- **WHEN** a interface AIAgentAdapter é inspecionada
- **THEN** os métodos `set_*_callback()` SHALL NOT existir
- **AND** os métodos `on()` e `emit()` SHALL existir
