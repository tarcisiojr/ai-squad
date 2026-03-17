## Why

O fluxo atual é fixo (PO → Dev → QA) e hardcoded no engine.py. Projetos diferentes precisam de agentes diferentes — um fintech precisa de Security, um app precisa de UX, um monorepo precisa de múltiplos Devs. Além disso, não há coordenação inteligente entre agentes: quem valida critérios de aceite, quem manda refazer, quem distribui tarefas entre devs paralelos. Precisamos de um agente coordenador — o Squad Lead — que substitui o engine como cérebro do fluxo.

## What Changes

- **BREAKING**: Novo agente obrigatório **Squad Lead** que coordena todo o fluxo de demandas — substitui o `run_demand_cycle` fixo do engine
- **BREAKING**: `personas` no config.yaml renomeado para `agents` — cada agente é definido por um AGENTS.md com formato padrão (domínio, quando envolver, critérios de aceite, marcador, instruções)
- **Squad Lead como padrão no Telegram** — mensagens sem comando vão para o Squad Lead; comandos `/<agente>` direcionam para agentes específicos
- **Agentes em paralelo** — Squad Lead pode invocar múltiplos agentes simultaneamente via `invoke_parallel`
- **Tools do Squad Lead** — `invoke_agent`, `invoke_parallel`, `get_status`, `check_workspace`
- **Engine vira runtime** — engine deixa de orquestrar e passa a executar o que o Squad Lead decide
- **Formato padrão de AGENTS.md** — seções obrigatórias: Domínio, Quando Envolver, Responsabilidades, Critérios de Aceite, Marcador de Conclusão, Restrições, Instruções
- **Agentes 100% configuráveis** — usuário cria quantos agentes quiser via AGENTS.md + config.yaml, zero hardcoded

## Capabilities

### New Capabilities
- `squad-lead`: Agente coordenador obrigatório que decide quais agentes envolver, em que ordem, valida critérios de aceite, e pode mandar refazer
- `agent-tools`: Tools disponíveis para o Squad Lead (invoke_agent, invoke_parallel, get_status, check_workspace)
- `parallel-agents`: Execução de múltiplos agentes em paralelo via asyncio.gather
- `agent-definition-format`: Formato padrão de AGENTS.md com seções obrigatórias para definição de agentes customizáveis

### Modified Capabilities
- `orchestrator`: Engine deixa de ter fluxo fixo — vira runtime que executa comandos do Squad Lead
- `platform-config`: `personas` renomeado para `agents`, novo campo `squad_lead`, agentes definidos por AGENTS.md
- `messaging-bus`: Mensagens sem comando vão para Squad Lead (não mais para fila de demandas genérica)

## Impact

- **engine.py** — remover `run_demand_cycle` fixo, adicionar `run_squad_lead`, implementar tools (invoke_agent, invoke_parallel, get_status, check_workspace)
- **daemon.py** — mensagem sem comando → Squad Lead; gerar comandos dos agents do config
- **factory.py** — `personas` → `agents`, novo campo `squad_lead`, carregar AGENTS.md de cada agente
- **config.yaml template** — reestruturar com `squad_lead` + `agents`
- **agents/** — novo `squad-lead/AGENTS.md`, reformatar todos os AGENTS.md no padrão
- **claude_agent_sdk.py** — suportar tools customizadas no adapter
- **team_manager.py** — copiar `agents/` com novo formato no create
