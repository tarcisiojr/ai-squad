## ADDED Requirements

### Requirement: Quant pesquisa dados de mercado do ativo
O Quant SHALL pesquisar via web dados quantitativos de preço, volume e risco do ativo.

#### Scenario: Pesquisa performance e momentum
- **WHEN** Quant recebe pedido de análise de um ativo
- **THEN** SHALL pesquisar em TradingView, Google Finance ou fontes equivalentes
- **THEN** SHALL coletar performance: 1 mês, 3 meses, 6 meses, 12 meses, YTD
- **THEN** SHALL identificar tendência de volume (crescente, estável, decrescente)

#### Scenario: Analisa suportes e resistências
- **WHEN** Quant coleta dados de preço
- **THEN** SHALL identificar principais suportes e resistências recentes
- **THEN** SHALL avaliar volatilidade e beta do ativo

#### Scenario: Emite veredicto de momentum
- **WHEN** análise quantitativa está completa
- **THEN** SHALL emitir veredicto: momentum positivo, neutro ou negativo
- **THEN** SHALL salvar relatório em analises/<ativo>/quantitativa.md
