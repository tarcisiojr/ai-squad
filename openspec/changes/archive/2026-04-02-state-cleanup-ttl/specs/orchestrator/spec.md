## MODIFIED Requirements

### Requirement: Persistência de estado
O orquestrador SHALL persistir o estado de cada demanda em arquivo JSON. O estado SHALL sobreviver a reinicializações do sistema. O orquestrador SHALL executar cleanup de demandas expiradas no boot e no início de cada nova demanda.

#### Scenario: Recuperação após reinício
- **WHEN** o sistema reinicia com uma demanda em estado `dev_working`
- **THEN** o orquestrador carrega o estado do JSON e retoma a partir de `dev_working`

#### Scenario: Cleanup no boot do daemon
- **WHEN** o daemon inicia
- **THEN** o orquestrador executa `cleanup_expired()` antes de processar novas mensagens

#### Scenario: Cleanup ao iniciar nova demanda
- **WHEN** uma nova demanda é recebida pelo engine
- **THEN** o orquestrador executa `cleanup_expired()` antes de processar a demanda
