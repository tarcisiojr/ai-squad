## ADDED Requirements

### Requirement: Serialização de acesso ao Squad Lead
O sistema SHALL usar um `asyncio.Semaphore(1)` para garantir que apenas uma execução do Squad Lead ocorra por vez. Mensagens que chegam enquanto o Squad Lead está ocupado SHALL aguardar na fila implícita do event loop.

#### Scenario: Duas mensagens simultâneas são serializadas
- **WHEN** mensagem A chega e o Squad Lead está processando
- **AND** mensagem B chega 2 segundos depois
- **THEN** mensagem B aguarda até mensagem A completar antes de ser processada

#### Scenario: Timeout na espera do semáforo
- **WHEN** uma mensagem aguarda mais de 30 segundos pelo semáforo
- **THEN** o sistema envia feedback "Aguardando Squad Lead finalizar tarefa anterior..." ao usuário

### Requirement: Estado como parâmetro
O método `run_squad_lead()` SHALL receber `user_id`, `demand_id` e `thread_id` como parâmetros explícitos. O sistema SHALL NOT armazenar esses valores como variáveis de instância mutáveis.

#### Scenario: Contexto isolado entre chamadas
- **WHEN** `run_squad_lead(user_id="A", demand_id="d1")` é chamado
- **AND** outra chamada com `user_id="B", demand_id="d2"` é enfileirada
- **THEN** cada chamada usa exclusivamente seus próprios parâmetros sem contaminação

#### Scenario: Variáveis de instância eliminadas
- **WHEN** o engine é inspecionado
- **THEN** os atributos `_default_user_id`, `_default_demand_id` e `_default_thread_id` SHALL NOT existir
