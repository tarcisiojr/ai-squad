## ADDED Requirements

### Requirement: Strategist consolida análises em tese de investimento
O Strategist SHALL ler os 3 relatórios (fundamentalista, quantitativa, macroeconômica) e consolidar em uma tese de investimento com recomendação.

#### Scenario: Consolida relatórios em tese
- **WHEN** Strategist recebe os 3 relatórios completos
- **THEN** SHALL gerar resumo executivo (3 parágrafos máximo)
- **THEN** SHALL listar pontos fortes e fracos do ativo
- **THEN** SHALL emitir recomendação: COMPRAR, MANTER ou VENDER
- **THEN** SHALL escrever tese em 1 frase (ex: "Petrobras negocia com desconto de 33% vs peers com cenário macro favorável")

#### Scenario: Inclui riscos e horizonte
- **WHEN** tese está sendo construída
- **THEN** SHALL listar top 3 riscos principais
- **THEN** SHALL definir horizonte recomendado: curto prazo (<6m), médio prazo (6-18m) ou longo prazo (>18m)

#### Scenario: Inclui disclaimer
- **WHEN** relatório final é gerado
- **THEN** SHALL incluir disclaimer: "Esta análise é gerada por IA e não constitui recomendação de investimento"
- **THEN** SHALL salvar em analises/<ativo>/tese-investimento.md

#### Scenario: Inclui tabela consolidada de indicadores
- **WHEN** tese está sendo construída
- **THEN** SHALL incluir tabela com principais indicadores do ativo vs setor
- **THEN** SHALL incluir dados de performance de preço
- **THEN** SHALL incluir resumo do cenário macro
