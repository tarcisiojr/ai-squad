## ADDED Requirements

### Requirement: Macro pesquisa cenário macroeconômico e setorial
O Macro SHALL pesquisar via web o cenário macroeconômico brasileiro e seu impacto no setor do ativo.

#### Scenario: Pesquisa indicadores macro
- **WHEN** Macro recebe pedido de análise de um ativo
- **THEN** SHALL pesquisar cenário atual: Selic, IPCA, câmbio (USD/BRL), PIB
- **THEN** SHALL usar fontes como BCB, IBGE, InfoMoney, Valor Econômico

#### Scenario: Avalia impacto setorial
- **WHEN** Macro identifica o setor do ativo
- **THEN** SHALL avaliar como o cenário macro impacta o setor específico
- **THEN** SHALL identificar riscos regulatórios ou políticos relevantes

#### Scenario: Pesquisa notícias recentes
- **WHEN** análise macro está em andamento
- **THEN** SHALL pesquisar notícias relevantes dos últimos 30 dias sobre o ativo e seu setor
- **THEN** SHALL emitir veredicto: cenário favorável, neutro ou adverso
- **THEN** SHALL salvar relatório em analises/<ativo>/macroeconomica.md
