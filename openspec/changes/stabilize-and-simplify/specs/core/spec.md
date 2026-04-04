## MODIFIED Requirements

### Requirement: Decomposição do Engine
O `engine.py` core SHALL ser reduzido a ≤600 linhas com responsabilidades: run_squad_lead, delegação de agentes, wiring de callbacks. Prompt building SHALL ser delegado ao `prompt_builder.py`. Pipeline callbacks SHALL ser delegados ao `pipeline_handler.py`. O engine SHALL expor `get_status() -> EngineStatus` como API pública para o daemon.

#### Scenario: Engine com responsabilidade focada
- **WHEN** engine.py é inspecionado
- **THEN** contém apenas: run_squad_lead, delegação, callbacks wiring, get_status
- **AND** tem ≤600 LOC

#### Scenario: Daemon usa API pública
- **WHEN** daemon.py precisa do status do engine
- **THEN** usa `engine.get_status()` que retorna `EngineStatus` dataclass
- **AND** daemon SHALL NOT acessar atributos prefixados com `_` do engine

### Requirement: Limpeza e Correções
Código morto SHALL ser removido: preset `personal-assistant`, passthrough methods que só delegam, `FEEDBACK_TIME_ONLY` hardcoded, `return ""` inalcançável. Imports inline SHALL ser movidos para nível de módulo.

#### Scenario: Preset personal-assistant removido
- **WHEN** o diretório `ai_squad/presets/` é inspecionado
- **THEN** `personal-assistant/` SHALL NOT existir

#### Scenario: Passthrough methods eliminados
- **WHEN** engine.py é inspecionado
- **THEN** métodos que apenas delegam sem adicionar lógica SHALL NOT existir

## ADDED Requirements

### Requirement: Daemon com responsabilidade focada
O daemon SHALL ter responsabilidades exclusivas de: lifecycle (start/stop), message routing (bus → engine), background tasks (heartbeat, healthcheck). Toda lógica de orquestração SHALL estar no engine. O daemon SHALL NOT acessar atributos privados do engine.

#### Scenario: Daemon não acessa _private do engine
- **WHEN** daemon.py é inspecionado via grep por `engine._`
- **THEN** zero ocorrências são encontradas

#### Scenario: Setup data-driven
- **WHEN** o daemon carrega env overrides
- **THEN** usa mapeamento declarativo (dict) em vez de blocos if/else repetitivos

### Requirement: RunnerContext enxuto
`RunnerContext` SHALL ter no máximo 5 campos: `adapter`, `message_bus`, `workspace`, `agent_timeout`, `personas`. Stores e outros serviços SHALL ser acessados via callbacks injetados pelo engine.

#### Scenario: RunnerContext com 5 campos
- **WHEN** `RunnerContext` é inspecionado
- **THEN** tem exatamente 5 campos
- **AND** não contém referências a journal, lessons, graph, daily_notes, conversation, reaction_tracker, context_collector ou pipeline_executor

### Requirement: Zero issues pyright/pylance
O código SHALL passar em `pyright ai_squad/` sem erros nem warnings. Type hints SHALL ser adicionados em todas as funções públicas.

#### Scenario: Pyright limpo
- **WHEN** `pyright ai_squad/` é executado
- **THEN** o resultado é 0 errors e 0 warnings

### Requirement: Cobertura de testes acima de 85%
O projeto SHALL manter cobertura de testes acima de 85% medida por `pytest --cov=ai_squad`. Toda nova funcionalidade SHALL ter testes correspondentes.

#### Scenario: Cobertura verificada
- **WHEN** `pytest --cov=ai_squad` é executado
- **THEN** a cobertura total é ≥85%

### Requirement: Código sem anti-patterns
O código SHALL seguir princípios SOLID, KISS, DRY e Clean Code. Especificamente: funções ≤30 linhas, sem god classes, sem estado mutável compartilhado, sem retry duplicado, sem boilerplate repetitivo, sem acesso a atributos privados de outros objetos.

#### Scenario: Funções dentro do limite
- **WHEN** qualquer função do projeto é inspecionada
- **THEN** tem no máximo 30 linhas (excluindo docstrings e linhas em branco)

#### Scenario: Sem acesso cross-object a privados
- **WHEN** o código é inspecionado via grep por `\.\_.+` entre módulos diferentes
- **THEN** nenhum módulo acessa atributos `_private` de objetos de outro módulo
