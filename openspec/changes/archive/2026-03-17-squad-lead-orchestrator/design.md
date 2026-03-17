## Context

O ai-dev-team orquestra agentes IA via Telegram dentro de Docker. O fluxo atual é fixo (PO → Dev → QA) controlado por código Python no engine.py. Projetos diferentes precisam de composições diferentes de agentes, e não há coordenação inteligente entre eles.

## Goals / Non-Goals

**Goals:**
- Squad Lead como agente coordenador que decide o fluxo dinamicamente
- Agentes 100% configuráveis via AGENTS.md + config.yaml
- Execução paralela de agentes quando o Squad Lead decidir
- Engine como runtime puro (executa, não decide)
- Mensagem sem comando → Squad Lead

**Non-Goals:**
- UI para criar agentes (v1 é editar arquivos)
- Squad Lead com memória entre demandas (cada demanda é independente)
- Priorização automática de demandas

## Decisions

### 1. Squad Lead usa tools para invocar agentes

**Escolha**: O Squad Lead é um agente Claude com tools customizadas. Quando precisa do PO, chama `invoke_agent("po", "Especificar...")`. O engine executa a tool e retorna o resultado.

**Alternativas**: Squad Lead gera plano estático; engine interpreta JSON de instrução

**Razão**: Tools dão ao Squad Lead controle total e reatividade. Ele pode mudar de ideia mid-flow (ex: Security reprovou, volta ao Dev). É o padrão nativo do Claude SDK.

### 2. invoke_agent inicia conversa agente ↔ usuario

**Escolha**: Quando o Squad Lead chama `invoke_agent("po", prompt)`, o PO conversa diretamente com o usuário via Telegram (modo CHAT/APPROVAL existente). Quando o PO marca conclusão, o resultado volta para o Squad Lead.

**Razão**: O usuário precisa interagir com cada agente (responder perguntas do PO, aprovar spec). O Squad Lead não intermedia — ele delega e valida o resultado.

### 3. invoke_parallel para execução simultânea

**Escolha**: Tool `invoke_parallel` recebe lista de agentes e prompts, executa via `asyncio.gather`. No Telegram, o usuário vê mensagens de múltiplos agentes e usa `/<comando>` para direcionar respostas.

**Razão**: Devs Frontend e Backend podem trabalhar ao mesmo tempo. Cada um mantém contexto independente via conversation store.

### 4. Formato padrao de AGENTS.md

**Escolha**: Cada agente é definido por um AGENTS.md com seções padronizadas:

```
# <Nome>
## Dominio
## Quando Envolver
## Responsabilidades
## Criterios de Aceite
## Marcador de Conclusao
## Restricoes
## Instrucoes
```

O engine lê todos os AGENTS.md e injeta um resumo (Domínio + Quando Envolver + Critérios) no prompt do Squad Lead.

**Razão**: Formato padronizado permite que o Squad Lead entenda qualquer agente novo sem mudança de código.

### 5. Config reestruturado

**Escolha**:
```yaml
squad_lead:
  name: "Squad Lead"
  avatar: "👨‍💼"

agents:
  po:
    name: "PO Agent"
    avatar: "📋"
    command: "/po"
  dev:
    name: "Dev Agent"
    avatar: "🔧"
    command: "/dev"
```

Agentes definidos em `agents/<nome>/AGENTS.md`. O config lista quais estão ativos.

**Razão**: Separação clara entre Squad Lead (obrigatório/fixo) e agentes (configuráveis/variáveis).

### 6. Engine vira runtime

**Escolha**: O engine não tem mais `run_demand_cycle` com fluxo fixo. Tem `run_squad_lead(demand_id, user_id, text)` que inicia o Squad Lead com tools e deixa ele decidir tudo.

**Razão**: Toda inteligência de orquestração está no Squad Lead (agente IA), não no código Python.

## Risks / Trade-offs

**[Squad Lead pode tomar decisões ruins]** → Mitigação: AGENTS.md do Squad Lead com instruções claras. Critérios de aceite de cada agente servem como checklist.

**[Paralelo no Telegram pode confundir usuario]** → Mitigação: cada mensagem tem label do agente. Usuário usa /<comando> para direcionar. Squad Lead pode consolidar.

**[Custo de tokens aumenta]** → Mitigação: Squad Lead é uma camada extra de LLM. Mas ele toma decisões melhores que código fixo. Usar model mais leve para Squad Lead se necessário.

**[Tools complexas no SDK]** → Mitigação: implementar como funções Python que o SDK chama via tool_use. O Claude Agent SDK suporta custom tools.
