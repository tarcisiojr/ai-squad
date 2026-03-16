## Why

Os agentes hoje operam sem memória: o PO não conhece o produto que está especificando, os artefatos gerados se perdem ao final do ciclo, e se o container reiniciar toda a conversa e progresso são perdidos. Para que o time de IA funcione como um time real de desenvolvimento, ele precisa produzir documentação persistente no repositório, conhecer o produto existente, e ser capaz de retomar trabalho interrompido.

## What Changes

- **Artefatos SDD no repositório alvo** — PO gera `specs/<demanda>/` (proposal.md, design.md, specs/) dentro de `/workspace`, criando histórico versionável no git do projeto
- **Contexto do produto para o PO** — antes de especificar, o agente PO lê código-fonte, specs existentes e README do repositório alvo para entender o que o produto faz
- **Persistência de histórico de conversa** — cada interação agente ↔ usuário é salva em `state/<demand_id>/conversation.json`, permitindo retomada após crash/restart
- **Retomada de demandas em andamento** — no startup, o daemon verifica demandas com estado não-terminal e retoma do último checkpoint
- **AGENTS.md com instruções de exploração** — PO recebe instrução para explorar o repo antes de fazer perguntas
- **Comandos `/po`, `/dev`, `/qa` com contexto** — agentes direcionados também recebem contexto do projeto

## Capabilities

### New Capabilities
- `demand-artifacts`: Geração e persistência de artefatos SDD (proposal, design, specs) dentro do repositório alvo em `specs/<demanda>/`
- `product-context`: Coleta e injeção de contexto do produto (README, estrutura, specs existentes) no prompt dos agentes antes de cada interação
- `conversation-persistence`: Salvamento do histórico de conversa por demanda em `state/<demand_id>/conversation.json` com checkpoint por etapa
- `demand-resume`: Detecção e retomada de demandas com estado não-terminal no startup do daemon

### Modified Capabilities
- `orchestrator`: Engine precisa salvar checkpoints entre etapas e suportar retomada parcial do ciclo de demanda
- `ai-agent-adapter`: Adapter precisa receber contexto do produto junto com o prompt

## Impact

- **engine.py** — salvar checkpoints, retomar ciclo parcial, injetar contexto do produto
- **daemon.py** — verificar demandas pendentes no startup, re-enfileirar para retomada
- **state.py** — novo formato de estado com conversation history e checkpoint
- **agents/po/AGENTS.md** — instruções para explorar repo antes de especificar
- **agents/dev-orchestrator/AGENTS.md** — instruções para gerar artefatos em specs/
- **factory.py** — suportar injeção de product context na criação do adapter
