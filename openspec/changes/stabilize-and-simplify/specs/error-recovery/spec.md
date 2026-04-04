## ADDED Requirements

### Requirement: Retry de timeout com budget
O sistema SHALL retentar operações que falham por timeout, usando o tempo restante do budget original como novo timeout. O número máximo de retries SHALL ser 2 (3 tentativas totais).

#### Scenario: Timeout retentado com sucesso
- **WHEN** um agente falha por timeout aos 250s de um budget de 300s
- **THEN** o sistema retenta com timeout de 50s (tempo restante)
- **AND** se a retentativa sucede, o resultado é processado normalmente

#### Scenario: Budget esgotado
- **WHEN** um agente falha por timeout e o tempo restante é menor que 30s
- **THEN** o sistema SHALL NOT retentar e propaga o erro para recovery

### Requirement: Circuit breaker para auto-recovery
O sistema SHALL implementar circuit breaker que interrompe cascata de falhas. Após 3 falhas consecutivas do Squad Lead em auto-recovery, o circuit breaker SHALL abrir e notificar o usuário.

#### Scenario: Circuit breaker abre após falhas consecutivas
- **WHEN** auto-recovery falha 3 vezes seguidas
- **THEN** o circuit breaker abre e envia mensagem ao usuário "Sistema pausado após falhas consecutivas. Envie nova mensagem para retomar."

#### Scenario: Circuit breaker reseta com sucesso
- **WHEN** o circuit breaker está aberto e o usuário envia nova mensagem
- **THEN** o circuit breaker reseta e processa a mensagem normalmente

### Requirement: Recuperação automática do bus
O daemon SHALL reconectar automaticamente o message bus em caso de desconexão, com backoff exponencial (2s, 4s, 8s, máximo 60s).

#### Scenario: Bus desconecta e reconecta
- **WHEN** `bus.run_forever()` falha com erro de conexão
- **THEN** o daemon aguarda 2s e tenta reconectar
- **AND** se falhar novamente, aguarda 4s, depois 8s, até máximo 60s

#### Scenario: Reconexão bem-sucedida reseta backoff
- **WHEN** o bus reconecta com sucesso após falha
- **THEN** o contador de backoff reseta para 2s
