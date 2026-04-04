## ADDED Requirements

### Requirement: Cache breakpoints no system prompt
O Claude adapter SHALL marcar o system prompt com `cache_control: {"type": "ephemeral"}` em chamadas à API Anthropic. Tokens cacheados SHALL ser reutilizados entre chamadas dentro da janela de cache (5 minutos).

#### Scenario: Chamadas consecutivas reutilizam cache
- **WHEN** duas chamadas ao Claude adapter ocorrem dentro de 5 minutos com o mesmo system prompt
- **THEN** a segunda chamada paga ~10% do custo dos tokens do system prompt

#### Scenario: Cache expira após inatividade
- **WHEN** mais de 5 minutos se passam entre chamadas
- **THEN** o system prompt é processado integralmente na próxima chamada

### Requirement: Cache breakpoints nas tool definitions
O Claude adapter SHALL marcar tool definitions com `cache_control: {"type": "ephemeral"}` quando suportado pela API. Tools são estáticas durante uma sessão e SHALL ser cacheadas.

#### Scenario: Tools cacheadas entre chamadas
- **WHEN** o Squad Lead é invocado múltiplas vezes na mesma demanda
- **THEN** as definições de tools são reutilizadas do cache nas chamadas subsequentes

### Requirement: Providers não-Anthropic ignoram caching
Adapters que não suportam prompt caching (Copilot, Agno) SHALL ignorar a funcionalidade sem erro. O caching SHALL ser específico do Claude adapter.

#### Scenario: Copilot adapter sem caching
- **WHEN** o sistema está configurado com `ai_provider: copilot`
- **THEN** nenhum cache_control é adicionado e o adapter funciona normalmente
