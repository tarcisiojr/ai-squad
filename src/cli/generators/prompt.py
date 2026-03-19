"""Template de prompt para geração de presets via IA."""

GENERATION_PROMPT = """\
Você é um arquiteto de times de IA. O usuário quer criar um time automatizado \
e descreveu o que precisa. Gere a configuração completa do time.

## Descrição do time
{description}

## Regras de geração

1. Gere entre 2 e 6 agentes especializados para o time descrito
2. Gere um pipeline com steps sequenciais (3-6 steps)
3. Pelo menos 1 step deve ser `type: checkpoint` (aprovação humana)
4. Cada agente deve ter um AGENTS.md com persona detalhada em português
5. Cada step deve ter quality gates e veto conditions
6. O squad-lead é OBRIGATÓRIO e coordena o time (não incluir no pipeline)
7. Nomes de agentes em kebab-case (ex: data-analyst, report-writer)
8. IDs de steps em snake_case sem acentos

## Formato de output

Responda APENAS com JSON válido, sem markdown, sem explicações. O JSON deve seguir \
exatamente esta estrutura:

{{
  "pipeline": {{
    "name": "Nome do Pipeline",
    "description": "Descrição do pipeline",
    "steps": [
      {{
        "id": "step_id",
        "name": "Nome do Step",
        "agent": "agent-name",
        "type": "agent|checkpoint",
        "execution": "subagent|background",
        "model_tier": "fast|powerful",
        "file": "steps/step-01-nome.md"
      }}
    ]
  }},
  "agents": {{
    "agent-name": {{
      "display_name": "Nome Exibição",
      "avatar": "emoji",
      "agents_md": "conteúdo completo do AGENTS.md"
    }}
  }},
  "squad_lead_md": "conteúdo do AGENTS.md do Squad Lead",
  "steps": {{
    "steps/step-01-nome.md": "conteúdo completo do step file"
  }}
}}

## Notas sobre os campos

- `agent`: pode ser string (1 agente) ou usar `agents` como lista para execução paralela
- `type`: "checkpoint" pausa para aprovação humana, "agent" avança automaticamente
- `execution`: "subagent" aguarda conclusão, "background" executa em paralelo
- `model_tier`: "powerful" para tarefas complexas, "fast" para simples
- Steps podem ter `on_reject: step_id` para loop de revisão

## Formato do AGENTS.md

Cada AGENTS.md deve conter estas seções em português:

```
# Nome do Agente

## Dominio
Descrição do domínio de atuação

## Quando Envolver
- Situações em que este agente deve ser acionado

## Responsabilidades
- Lista de responsabilidades

## Criterios de Aceite
- Critérios verificáveis de conclusão

## Restricoes
- O que o agente NÃO deve fazer

## Instrucoes
Instruções detalhadas passo a passo

## Comunicacao
- Regras de comunicação (português brasileiro, respostas claras)
```

## Formato dos step files

Cada step file deve conter:

```
# Step NN: Nome (Agente)

## Inputs
- O que o step recebe do anterior

## Expected Outputs
- Artefatos esperados

## Quality Gate
- [ ] Checklist de verificação

## Veto Conditions
- Condições que reprovam automaticamente
```

## Exemplo de referência (preset dev-openspec)

### pipeline.yaml
```yaml
name: "Dev OpenSpec"
description: >
  Pipeline de desenvolvimento orientado a especificação.

pipeline:
  steps:
    - id: especificacao
      name: "Especificação"
      agent: po
      type: checkpoint
      execution: subagent
      model_tier: powerful
      file: steps/step-01-spec.md

    - id: implementacao
      name: "Implementação"
      agents: [dev-backend, dev-frontend]
      type: agent
      execution: background
      model_tier: powerful
      file: steps/step-02-dev.md

    - id: revisao
      name: "Revisão de Código"
      agent: code-review
      type: checkpoint
      execution: subagent
      model_tier: powerful
      on_reject: implementacao
      max_review_cycles: 3
      file: steps/step-03-review.md

    - id: qualidade
      name: "QA"
      agent: qa
      type: agent
      execution: subagent
      model_tier: powerful
      file: steps/step-04-qa.md
```

Agora gere o JSON para o time descrito acima.
"""


def build_generation_prompt(description: str) -> str:
    """Monta o prompt de geração com a descrição do usuário."""
    return GENERATION_PROMPT.format(description=description)
