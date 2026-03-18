# Proposal: Preset Investment Analysis

## Why

O ai-squad hoje tem apenas presets de desenvolvimento de software (`dev-openspec`, `infra-monitor`). Para demonstrar que a plataforma é **agnóstica ao domínio**, precisamos de um preset fora do contexto de código.

Análise de investimentos é um caso perfeito — envolve pesquisa paralela, consolidação e revisão, tudo coordenado pelo Squad Lead via pipeline declarativo.

## What Changes

### Novo preset `investment-analysis`

Preset com 5 agentes especializados e pipeline de 3 etapas que analisa ativos do mercado brasileiro (B3).

### Fluxo

```
Usuário: "Analisa PETR4"
     │
     ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Analyst │  │  Quant  │  │  Macro  │
│ fundam. │  │ técnica │  │ cenário │
└────┬────┘  └────┬────┘  └────┬────┘
     │  background (paralelo)  │
     └────────┬───┘────────────┘
              ▼
      ┌──────────────┐
      │  Strategist  │
      │ consolida    │
      │ recomendação │
      └──────┬───────┘
             ▼
      ┌──────────────┐
      │Risk Reviewer │ ── rejeita → Strategist refaz
      │ checkpoint   │
      └──────┬───────┘
             ▼
      Relatório final
      ao usuário
```

### Entregáveis (markdown)

```
analises/<ativo>/
├── fundamentalista.md    ← balanço, indicadores, peers
├── quantitativa.md       ← preço, momentum, volatilidade
├── macroeconomica.md     ← Selic, setor, riscos
└── tese-investimento.md  ← consolidação + recomendação final
```

## Capabilities

### analyst-agent
Agente fundamentalista que pesquisa dados financeiros (StatusInvest, Fundamentus, RI da empresa), calcula indicadores (P/L, EV/EBITDA, ROE, dividend yield, endividamento) e compara com peers do setor.

### quant-agent
Agente quantitativo que pesquisa dados de mercado (preço, volume, volatilidade), analisa performance em múltiplos períodos, identifica suportes/resistências e avalia momentum.

### macro-agent
Agente macroeconômico que pesquisa cenário macro (Selic, IPCA, câmbio), impacto setorial, riscos regulatórios/políticos e notícias recentes.

### strategist-agent
Agente estrategista que lê os 3 relatórios, consolida em tese de investimento com recomendação (COMPRAR/MANTER/VENDER), preço-alvo relativo e horizonte temporal.

### risk-review-agent
Agente revisor que questiona a tese (devil's advocate), valida coerência dos dados, verifica viés de confirmação e cenários adversos.

### investment-pipeline
Pipeline de 3 steps: pesquisa paralela → tese → revisão de risco (com loop on_reject).

## Impact

### Arquivos novos
- `src/presets/investment-analysis/pipeline/pipeline.yaml`
- `src/presets/investment-analysis/pipeline/steps/step-01-research.md`
- `src/presets/investment-analysis/pipeline/steps/step-02-thesis.md`
- `src/presets/investment-analysis/pipeline/steps/step-03-risk-review.md`
- `src/presets/investment-analysis/agents/squad-lead/AGENTS.md`
- `src/presets/investment-analysis/agents/analyst/AGENTS.md`
- `src/presets/investment-analysis/agents/quant/AGENTS.md`
- `src/presets/investment-analysis/agents/macro/AGENTS.md`
- `src/presets/investment-analysis/agents/strategist/AGENTS.md`
- `src/presets/investment-analysis/agents/risk-reviewer/AGENTS.md`

### Sem impacto
- Engine, daemon, CLI, adapters — tudo funciona com o novo preset sem mudança
- Presets existentes — sem alteração

## Non-Goals

- Integração com APIs financeiras (Yahoo Finance, CVM) — usa web search
- Gráficos ou visualizações — entregável é markdown
- Execução automática de ordens — apenas análise e recomendação
- Cobertura de mercados internacionais — foco B3
