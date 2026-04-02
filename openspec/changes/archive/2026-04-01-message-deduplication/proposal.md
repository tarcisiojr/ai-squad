# Proposal: Message Deduplication

## Problema

Hoje existem **3 caminhos simultâneos** que enviam a mesma informação ao usuário quando um agente conclui uma tarefa:

1. **`report_progress`** — agente reporta progresso em tempo real direto ao usuário (`engine.py:245-263`)
2. **`on_agent_done`** — `agent_runner.py:313-318` envia resultado bruto (até 2000 chars) direto ao usuário
3. **Squad Lead re-triggered** — `agent_runner.py:321-324` dispara o Squad Lead, que recebe o histórico de conversa (já contendo o resultado do agente em `agent_runner.py:304-311`) e naturalmente repete/parafraseia o conteúdo

Resultado: o usuário lê a mesma informação **3 vezes**, poluindo a conversa e dificultando o acompanhamento de demandas complexas.

## Solução

Implementar separação de **canal interno** (agentes ↔ orquestrador) e **canal externo** (orquestrador → usuário), inspirado nos padrões de mercado:

- **LangGraph** — supervisor decide se repassa literal (forward) ou resume o resultado
- **OpenHands** — sub-agentes são conversas isoladas, invisíveis ao usuário
- **CrewAI** — modo hierárquico com verbose=false esconde internals
- **AutoGen** — event stream com filtro na camada de apresentação

### Princípios

1. **`report_progress` vira canal interno** — progresso do agente vai pro Squad Lead como contexto, não direto ao usuário
2. **Status leve durante execução** — substituir report_progress detalhado por indicador curto ("⚙️ Dev Backend trabalhando...")
3. **Squad Lead como porta-voz** — recebe resultado do agente e decide: repassar literal (forward) ou resumir
4. **Nunca repetir conteúdo** — Squad Lead instrução explícita no prompt para não parafrasear o que já foi comunicado
5. **Decisão de próximo passo sempre concisa** — "Próximo: QA vai validar" sem repetir o que foi feito

## Escopo

### Inclui
- Remover envio direto do resultado no `on_agent_done`
- Redirecionar `report_progress` como canal interno (Squad Lead recebe, não o usuário)
- Adicionar indicador de status leve durante execução do agente
- Instruções anti-repetição no prompt do Squad Lead
- Lógica de forward vs resume no Squad Lead

### Não inclui
- Mudanças na interface do MessageBus
- Alterações no Telegram/CLI bus
- Mudanças no pipeline ou quality gates
- Refatoração de adapters

## Impacto

- **Redução de ~60-70% do texto** na conversa por ciclo de agente
- Conversas mais objetivas e fáceis de acompanhar
- Squad Lead com papel mais claro de consolidador
- Mantém visibilidade (status leve + resultado via Squad Lead)
