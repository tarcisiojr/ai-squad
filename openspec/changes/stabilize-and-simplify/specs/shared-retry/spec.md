## ADDED Requirements

### Requirement: Função retry_with_backoff compartilhada
O sistema SHALL ter uma única função `retry_with_backoff(fn, max_retries, base_delay, is_transient)` em `ai_squad/common/retry.py`. Tanto o adapter quanto o agent_runner SHALL usar esta função para retry.

#### Scenario: Retry com backoff exponencial
- **WHEN** `fn` falha com erro transiente na primeira tentativa
- **THEN** aguarda `base_delay` segundos e retenta
- **AND** se falhar novamente, aguarda `base_delay * 2` segundos

#### Scenario: Erro não-transiente não é retentado
- **WHEN** `fn` falha com erro que `is_transient()` retorna False
- **THEN** o erro é propagado imediatamente sem retry

#### Scenario: Máximo de retries respeitado
- **WHEN** `fn` falha `max_retries + 1` vezes consecutivas com erros transientes
- **THEN** o último erro é propagado

### Requirement: Eliminação de retry duplicado
A lógica de retry em `claude_agent_sdk.py` e `agent_runner.py` SHALL ser substituída por chamadas a `retry_with_backoff()`. O sistema SHALL NOT conter implementações duplicadas de retry.

#### Scenario: Adapter usa retry compartilhado
- **WHEN** o adapter executa uma chamada ao SDK
- **THEN** usa `retry_with_backoff()` de `ai_squad/common/retry.py`

#### Scenario: Runner usa retry compartilhado
- **WHEN** o agent_runner executa um agente
- **THEN** usa `retry_with_backoff()` de `ai_squad/common/retry.py`
