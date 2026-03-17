## ADDED Requirements

### Requirement: Mensagens do usuario nunca bloqueiam
O daemon SHALL processar mensagens do usuario imediatamente, sem esperar demandas em andamento.

#### Scenario: Usuario envia mensagem durante execucao de agente
- **WHEN** um agente esta executando em background e o usuario envia uma mensagem
- **THEN** o daemon MUST processar a mensagem imediatamente via Squad Lead e retornar resposta

#### Scenario: Usuario pergunta status durante execucao
- **WHEN** o usuario envia "Quais agents estao ativos?" enquanto PO esta rodando
- **THEN** o Squad Lead MUST responder com o estado atual dos agentes em poucos segundos

### Requirement: Squad Lead responde rapido
O Squad Lead SHALL ser executado com max_turns baixo (3-5) para garantir resposta rapida.

#### Scenario: Resposta em tempo aceitavel
- **WHEN** o usuario envia uma mensagem ao Squad Lead
- **THEN** o Squad Lead MUST responder em menos de 30 segundos (nao minutos)

#### Scenario: Squad Lead delega em vez de executar
- **WHEN** o usuario pede uma demanda complexa
- **THEN** o Squad Lead MUST usar start_agent para delegar e retornar resposta imediata ao usuario, sem tentar executar tudo sozinho
