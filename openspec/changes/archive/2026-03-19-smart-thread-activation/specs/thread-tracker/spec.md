## ADDED Requirements

### Requirement: Estados de thread
O sistema DEVE manter estado por thread_id com transições: INACTIVE → ACTIVE → STANDBY, e STANDBY → ACTIVE via re-convocação.

#### Scenario: Thread inativa (nunca chamado)
- **WHEN** uma mensagem chega numa thread onde o bot nunca foi mencionado
- **THEN** o estado da thread é INACTIVE e o bot ignora

#### Scenario: Ativação por menção
- **WHEN** uma mensagem menciona @bot numa thread (qualquer estado)
- **THEN** o estado da thread transita para ACTIVE

#### Scenario: Bot ativo responde na thread
- **WHEN** o estado da thread é ACTIVE e uma mensagem chega na thread
- **THEN** o bot processa a mensagem (thread_follow)

### Requirement: Handoff automático para humano
O sistema DEVE transitar para STANDBY quando um humano responde numa thread ACTIVE sem mencionar o bot.

#### Scenario: Humano responde sem menção
- **WHEN** thread está ACTIVE e um humano (não bot) envia mensagem sem @bot
- **THEN** o estado transita para STANDBY e o bot envia mensagem de handoff

#### Scenario: Mensagem de handoff
- **WHEN** o bot transita para STANDBY
- **THEN** o bot envia mensagem informando quem assumiu e como re-convocar (ex: "João assumiu. Me mencione se precisar.")

#### Scenario: Handoff message desabilitado
- **WHEN** `thread_tracking.handoff_message: false` no config.yaml
- **THEN** o bot transita para STANDBY silenciosamente (sem enviar mensagem)

### Requirement: Bot em standby ignora mensagens
O sistema DEVE ignorar mensagens na thread quando o estado é STANDBY, exceto se o bot for mencionado.

#### Scenario: Mensagem em thread standby sem menção
- **WHEN** thread está em STANDBY e uma mensagem sem @bot chega
- **THEN** o bot ignora a mensagem

#### Scenario: Re-convocação em thread standby
- **WHEN** thread está em STANDBY e uma mensagem com @bot chega
- **THEN** o estado transita para ACTIVE e o bot processa a mensagem

### Requirement: Timeout de standby
O sistema DEVE oferecer ajuda se o humano que assumiu ficou inativo por `standby_timeout` segundos.

#### Scenario: Humano inativo após timeout
- **WHEN** thread está em STANDBY e `standby_timeout` (default: 1800s) se passou sem atividade humana
- **THEN** o bot envia mensagem oferecendo ajuda (ex: "Sem atualizações há 30min. Precisa de ajuda?")

#### Scenario: Timeout configurável
- **WHEN** `thread_tracking.standby_timeout: 3600` no config.yaml
- **THEN** o timeout de standby é 60 minutos em vez do default 30

### Requirement: Persistência de estado
O estado das threads DEVE ser persistido em `state/threads.json` usando escrita atômica e sobreviver a restarts.

#### Scenario: Estado carregado no startup
- **WHEN** o daemon inicia e `state/threads.json` existe
- **THEN** o ThreadTracker carrega os estados das threads do arquivo

#### Scenario: Estado salvo após transição
- **WHEN** o estado de uma thread muda (ACTIVE → STANDBY ou vice-versa)
- **THEN** o `state/threads.json` é atualizado atomicamente via write_json_atomic

#### Scenario: Limpeza de threads inativas
- **WHEN** o daemon inicia e existem threads com última atividade > `inactive_thread_ttl` (default: 86400s)
- **THEN** essas threads são removidas do estado

### Requirement: Configuração de tempos
O sistema DEVE suportar seção `thread_tracking` no config.yaml com tempos configuráveis e defaults sensatos.

#### Scenario: Defaults aplicados
- **WHEN** o config.yaml não define seção `thread_tracking`
- **THEN** o sistema usa: standby_timeout=1800, inactive_thread_ttl=86400, handoff_message=true

#### Scenario: Configuração custom
- **WHEN** o config.yaml define `thread_tracking.standby_timeout: 900`
- **THEN** o timeout de standby é 15 minutos

### Requirement: Convocação para registro de aprendizado
O sistema DEVE permitir que o bot seja re-convocado via @mention ao final de uma thread para registrar aprendizados, independente do estado atual da thread.

#### Scenario: Registro de aprendizado pós-resolução
- **WHEN** uma thread está em STANDBY (humano resolveu) e alguém menciona @bot pedindo para registrar
- **THEN** o bot transita para ACTIVE, processa a mensagem e pode usar learn_lesson para registrar

#### Scenario: Aprendizado disponível para próximos incidentes
- **WHEN** um aprendizado é registrado via learn_lesson numa thread
- **THEN** em futuras threads com problemas similares, o bot pode recuperar esse aprendizado via busca FTS5
