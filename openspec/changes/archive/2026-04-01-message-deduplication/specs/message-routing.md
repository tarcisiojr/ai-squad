# Spec: Message Routing

## Requisitos

### Canal Interno (agente → Squad Lead)

- **REQ-01**: `report_progress` do agente NÃO deve enviar mensagem direto ao usuário
- **REQ-02**: `report_progress` deve armazenar o progresso no contexto do Squad Lead (ex: campo no RunningAgent)
- **REQ-03**: Resultado do agente no `on_agent_done` NÃO deve ser enviado direto ao usuário
- **REQ-04**: Resultado do agente deve ser passado ao Squad Lead como contexto para decisão

### Canal Externo (Squad Lead → usuário)

- **REQ-05**: Durante execução do agente, enviar status leve ao usuário ("⚙️ {label} trabalhando...")
- **REQ-06**: Squad Lead deve ser o único ponto que comunica resultados de agentes ao usuário
- **REQ-07**: Squad Lead deve decidir entre forward (repassar literal) ou resume (resumir) o resultado
- **REQ-08**: Squad Lead NUNCA deve parafrasear conteúdo que já foi comunicado ao usuário

### Prompt do Squad Lead

- **REQ-09**: Prompt do Squad Lead deve conter instrução explícita anti-repetição
- **REQ-10**: Ao receber resultado de agente, prompt deve instruir: "apresente o resultado de forma concisa, sem repetir o que já foi reportado via status"
- **REQ-11**: Decisão de próximo passo deve ser separada do resultado (ex: "Próximo: QA vai validar")

## Cenários

### Cenário 1: Agente conclui com sucesso
```
DADO que o agente Dev Backend está executando uma tarefa
QUANDO o agente chama report_progress("Analisando 15 arquivos...")
ENTÃO o usuário vê: "⚙️ Dev Backend trabalhando..."
  E o Squad Lead recebe internamente: "Analisando 15 arquivos..."

QUANDO o agente conclui com resultado "Encontrei 3 bugs no módulo X"
ENTÃO o resultado NÃO é enviado direto ao usuário
  E o Squad Lead é disparado com o resultado como contexto
  E o Squad Lead envia ao usuário: "Dev Backend encontrou 3 bugs no módulo X. Próximo: QA vai validar."
```

### Cenário 2: Agente falha
```
DADO que o agente Dev Backend está executando
QUANDO o agente falha com erro "timeout ao acessar API"
ENTÃO o Squad Lead é disparado com o erro como contexto
  E o Squad Lead envia: "Dev Backend encontrou um problema (timeout na API). Vou retentar com timeout maior."
```

### Cenário 3: Múltiplos report_progress
```
DADO que o agente envia 5 report_progress durante execução
QUANDO o Squad Lead recebe todos os 5
ENTÃO o usuário vê apenas 1 status leve ("⚙️ Dev Backend trabalhando...")
  E o Squad Lead tem acesso aos 5 como contexto interno
```

### Cenário 4: Resultado longo do agente
```
DADO que o agente produz resultado com 3000+ caracteres
QUANDO o Squad Lead recebe o resultado
ENTÃO o Squad Lead resume em no máximo 500 caracteres
  E inclui indicação de que detalhes estão nos artefatos
```
