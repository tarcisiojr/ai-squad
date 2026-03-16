# Spec: Intent Classifier

## Objetivo
Squad Lead deve classificar a intenção do usuário ANTES de decidir a ação, evitando tratar perguntas como demandas.

## Categorias de Intent

| Intent | Exemplos | Ação esperada |
|--------|----------|---------------|
| `question` | "Como funciona X?", "O que é Y?" | Responder diretamente, sem delegar |
| `status` | "Como tá?", "Status?", "Já terminou?" | Chamar `get_demand_state()` e responder |
| `demand` | "Cria um endpoint de login", "Adiciona feature X" | Delegar via `start_agent("po", ...)` |
| `resume` | "Continua", "Retoma", "E aquele PR?" | Consultar estado e retomar de onde parou |
| `approval` | "Aprovado", "OK", "Pode seguir" | Avançar estado da demanda pendente |
| `rejection` | "Não", "Refaz", "Não era isso" | Re-delegar ao agente da fase atual |
| `visual` | "Mostra como ficou", "Screenshot" | Usar playwright-cli diretamente |

## Implementação

### Onde: AGENTS.md do Squad Lead
Adicionar seção de classificação como PRIMEIRA instrução, antes do fluxo de demandas.

### Regra
```
ANTES de qualquer ação, classifique a mensagem:

1. É PERGUNTA? (contém "?", pede explicação, não pede ação)
   → Responda diretamente. NÃO delegue.

2. É STATUS? (pergunta sobre andamento)
   → Chame get_demand_state() e responda.

3. É RETOMADA? (referencia trabalho anterior)
   → Consulte estado, retome de onde parou.

4. É APROVAÇÃO/REJEIÇÃO? (resposta a pedido anterior)
   → Avance ou re-delegue conforme o caso.

5. É DEMANDA? (pede algo novo para ser feito)
   → Delegue via start_agent("po", ...).
```

## Critérios de Aceite

- [ ] Pergunta "O que é o barramento?" NÃO dispara start_agent
- [ ] Pergunta "Como tá a demanda?" retorna status real do state/
- [ ] Mensagem "Continua" retoma demanda parada sem criar nova
- [ ] Mensagem "Cria endpoint de login" delega ao PO normalmente
- [ ] Mensagem "Aprovado" avança demanda em awaiting_plan_approval
- [ ] Mensagem "Refaz isso" re-delega ao agente da fase atual
