# Tasks: preset-investment-analysis

## Pipeline

- [x] Criar `src/presets/investment-analysis/pipeline/pipeline.yaml` com 3 steps (research, thesis, risk-review)
- [x] Criar `src/presets/investment-analysis/pipeline/steps/step-01-research.md` — quality gate: 3 relatórios existem
- [x] Criar `src/presets/investment-analysis/pipeline/steps/step-02-thesis.md` — quality gate: tese-investimento.md existe com recomendação
- [x] Criar `src/presets/investment-analysis/pipeline/steps/step-03-risk-review.md` — quality gate: veredicto APROVADO ou REJEITADO

## Agentes

- [x] Criar `src/presets/investment-analysis/agents/squad-lead/AGENTS.md` — coordenador financeiro, classifica pedidos de análise
- [x] Criar `src/presets/investment-analysis/agents/analyst/AGENTS.md` — fundamentalista, pesquisa balanço/indicadores/peers
- [x] Criar `src/presets/investment-analysis/agents/quant/AGENTS.md` — quantitativo, pesquisa preço/volume/momentum
- [x] Criar `src/presets/investment-analysis/agents/macro/AGENTS.md` — macroeconômico, pesquisa Selic/IPCA/câmbio/setor
- [x] Criar `src/presets/investment-analysis/agents/strategist/AGENTS.md` — consolida análises, gera recomendação
- [x] Criar `src/presets/investment-analysis/agents/risk-reviewer/AGENTS.md` — devil's advocate, valida tese

## CLI — suporte ao novo preset

- [x] Adicionar flag `--preset` ao comando `create` (default: dev-openspec)
- [x] `ai-squad create MeuTime --preset investment-analysis` copia o preset correto
- [x] Testes: criação de time com preset investment-analysis

## Testes

- [x] Teste: pipeline.yaml do preset carrega corretamente via PipelineLoader
- [x] Teste: step files parseiam quality gates e veto conditions
- [x] Teste: create com --preset copia agents e pipeline corretos
