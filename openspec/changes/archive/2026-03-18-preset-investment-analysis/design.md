## Context

O ai-squad tem presets para desenvolvimento (`dev-openspec`, `infra-monitor`). Queremos demonstrar que a plataforma é agnóstica ao domínio com um preset de análise de investimentos focado no mercado brasileiro (B3). Os agentes usam web search como ferramenta principal — sem integração com APIs financeiras.

O pipeline já suporta execução em paralelo (background), checkpoints e loops de revisão (on_reject). A estrutura de presets é copiável: diretório com agents/ e pipeline/.

## Goals / Non-Goals

**Goals:**
- Criar preset `investment-analysis` com 5 agentes + squad-lead
- Pipeline de 3 steps: pesquisa paralela → tese → revisão de risco
- Entregável em markdown: relatórios individuais + tese consolidada
- Agentes pesquisam via web search (StatusInvest, Fundamentus, InfoMoney, etc.)
- Focado em ativos da B3

**Non-Goals:**
- Integração com APIs financeiras (Yahoo Finance, CVM, Bloomberg)
- Gráficos ou visualizações
- Execução de ordens de compra/venda
- Mercados internacionais

## Decisions

### 1. Estrutura de entregáveis por ativo

**Decisão:** Cada análise gera um diretório `analises/<ativo>/` com 4 arquivos markdown.

```
analises/PETR4/
├── fundamentalista.md    ← Analyst
├── quantitativa.md       ← Quant
├── macroeconomica.md     ← Macro
└── tese-investimento.md  ← Strategist (consolidação final)
```

**Justificativa:** Separação clara por especialidade. O Strategist lê os 3 relatórios para consolidar. O usuário pode ler cada análise individualmente ou apenas a tese final.

### 2. Três analistas em paralelo (background)

**Decisão:** Step 1 (research) usa `execution: background` com 3 agentes: analyst, quant, macro.

**Alternativa considerada:** Execução sequencial (analyst → quant → macro). Rejeitada porque as análises são independentes — paralelo reduz tempo total de ~15min para ~5min.

### 3. Risk Reviewer como devil's advocate

**Decisão:** O Risk Reviewer não faz análise própria — ele questiona a tese do Strategist. Se encontrar falhas, rejeita e o Strategist refaz com o feedback.

**Justificativa:** Evita viés de confirmação. O Strategist tende a criar uma narrativa coerente; o Risk Reviewer testa a robustez dessa narrativa.

### 4. Squad Lead adaptado para contexto financeiro

**Decisão:** O Squad Lead desse preset classifica pedidos de análise (ativo, setor, comparativo) e conhece o fluxo financeiro. Não é o mesmo AGENTS.md do dev-openspec.

**Justificativa:** Um Squad Lead de dev não sabe delegar análise fundamentalista. Cada preset tem seu próprio Squad Lead com instruções específicas do domínio.

### 5. Web search como única fonte de dados

**Decisão:** Agentes usam a tool `WebSearchTool` (já disponível no Claude Agent SDK) para pesquisar dados em sites como StatusInvest, Fundamentus, TradingView, InfoMoney, Valor Econômico, BCB.

**Justificativa:** Zero setup para o usuário. Sem API keys adicionais, sem integrações. Os sites financeiros brasileiros têm dados públicos acessíveis via search.

## Risks / Trade-offs

- **[Risco] Dados desatualizados via web search** → Mitigação: agentes instruídos a verificar data dos dados e alertar quando não conseguirem dados recentes
- **[Risco] Sites bloqueiam scraping** → Mitigação: web search retorna snippets, não scraping direto; múltiplas fontes como fallback
- **[Trade-off] Sem dados em tempo real (preço atual)** → Aceito; análise fundamentalista não exige preço ao segundo
- **[Risco] Alucinação em indicadores financeiros** → Mitigação: agentes instruídos a citar fonte de cada dado; Risk Reviewer valida coerência
