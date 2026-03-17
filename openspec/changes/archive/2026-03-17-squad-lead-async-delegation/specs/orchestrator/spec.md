## MODIFIED Requirements

### Requirement: Despacho de agentes via adapter
O orquestrador SHALL disparar agentes em background como asyncio tasks, em vez de bloquear o loop principal. O orquestrador SHALL manter registro dos agentes em execucao com estado, tempo e resultado.

#### Scenario: Despacho de agente PO em background
- **WHEN** o Squad Lead chama start_agent("po", prompt)
- **THEN** o orquestrador MUST criar asyncio task para o PO, registrar em _running_agents, e retornar imediatamente

#### Scenario: Multiplos agentes em paralelo
- **WHEN** o Squad Lead inicia Dev e QA ao mesmo tempo
- **THEN** o orquestrador MUST executar ambos como asyncio tasks independentes em paralelo

#### Scenario: Agente conclui em background
- **WHEN** um agente background termina a execucao
- **THEN** o orquestrador MUST atualizar status para done, salvar resultado, notificar usuario, e disparar Squad Lead para decidir proximo passo

### Requirement: Roteamento de decisões humanas
O orquestrador SHALL rotear decisoes humanas durante execucao de agentes background via barramento. Agentes em background que precisam de input do usuario MUST pausar e aguardar resposta.

#### Scenario: Agente background solicita aprovacao
- **WHEN** um agente PO em background inclui marcador de conclusao
- **THEN** o orquestrador MUST enviar pedido de aprovacao ao usuario via barramento e aguardar resposta antes de concluir
