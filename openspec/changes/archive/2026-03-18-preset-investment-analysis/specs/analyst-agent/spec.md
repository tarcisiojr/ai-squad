## ADDED Requirements

### Requirement: Analyst pesquisa fundamentos do ativo
O Analyst SHALL pesquisar via web dados fundamentalistas do ativo solicitado no mercado brasileiro (B3).

#### Scenario: Pesquisa indicadores fundamentalistas
- **WHEN** Analyst recebe pedido de análise de um ativo (ex: PETR4)
- **THEN** SHALL pesquisar em StatusInvest, Fundamentus ou fontes equivalentes
- **THEN** SHALL coletar: receita, EBITDA, lucro líquido (evolução mínimo 3 anos)
- **THEN** SHALL calcular/coletar: P/L, P/VP, EV/EBITDA, ROE, dividend yield, dív. líquida/EBITDA

#### Scenario: Compara com peers do setor
- **WHEN** Analyst coleta indicadores do ativo
- **THEN** SHALL identificar 3-4 empresas peers do mesmo setor
- **THEN** SHALL comparar indicadores do ativo com média dos peers
- **THEN** SHALL emitir veredicto: barato, justo ou caro em relação ao setor

#### Scenario: Gera relatório em markdown
- **WHEN** pesquisa e comparação estão completas
- **THEN** SHALL salvar relatório em analises/<ativo>/fundamentalista.md
- **THEN** relatório SHALL citar fonte de cada dado coletado
