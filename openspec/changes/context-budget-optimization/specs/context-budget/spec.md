## ADDED Requirements

### Requirement: Estimativa de tokens por texto
O sistema SHALL estimar a contagem de tokens de um texto usando divisão por caracteres (`len(text) // 3`). A estimativa SHALL ter precisão mínima de 80% para textos em português e código misto.

#### Scenario: Estimativa de texto em português
- **WHEN** um texto de 3000 caracteres em português é submetido ao estimador
- **THEN** o estimador retorna ~1000 tokens (±20%)

#### Scenario: Estimativa de código Python
- **WHEN** um bloco de 1500 caracteres de código Python é submetido
- **THEN** o estimador retorna ~500 tokens (±20%)

### Requirement: Distribuição de tokens por tiers
O `ContextBudget` SHALL distribuir tokens em 3 tiers com prioridades distintas: Tier 1 (crítico, sempre presente), Tier 2 (relevante, encolhível), Tier 3 (complementar, descartável). Tier 1 SHALL nunca ser truncado. Tier 2 SHALL encolher via `shrink_fn` quando o budget não comporta o conteúdo completo, na ordem inversa de prioridade. Tier 3 SHALL ser incluído apenas se sobrar budget após Tiers 1 e 2.

#### Scenario: Budget suficiente para todos os tiers
- **WHEN** o budget total é 8000 tokens e a soma de todos os tiers é 6000 tokens
- **THEN** todos os componentes dos 3 tiers são incluídos no prompt final

#### Scenario: Budget insuficiente para Tier 3
- **WHEN** o budget total é 8000 tokens, Tier 1 usa 3000 e Tier 2 usa 4500
- **THEN** Tier 3 é completamente descartado e o prompt final contém apenas Tiers 1 e 2

#### Scenario: Budget insuficiente para Tier 2 completo
- **WHEN** o budget total é 8000 tokens, Tier 1 usa 3500 e Tier 2 completo usaria 6000
- **THEN** componentes do Tier 2 são encolhidos via shrink_fn na ordem inversa de prioridade até caber no budget restante de 4500

#### Scenario: Tier 1 excede budget total
- **WHEN** o budget total é 4000 tokens e Tier 1 requer 5000 tokens
- **THEN** o sistema emite warning no log e inclui Tier 1 completo (nunca trunca crítico)

### Requirement: Budget diferenciado por papel
O sistema SHALL aplicar budgets diferentes conforme o papel do consumidor: Squad Lead (8000 tokens), Agent tarefa (4000 tokens), Agent review (6000 tokens). O papel SHALL ser determinado pelo contexto da invocação.

#### Scenario: Squad Lead recebe budget completo
- **WHEN** o engine monta prompt para o Squad Lead
- **THEN** o ContextBudget é inicializado com total_budget=8000

#### Scenario: Agente de tarefa recebe budget reduzido
- **WHEN** o agent_runner monta prompt para um agente de tarefa
- **THEN** o ContextBudget é inicializado com total_budget=4000

### Requirement: Shrink functions por componente
Cada componente do Tier 2 SHALL ter uma `shrink_fn` que reduz seu conteúdo para caber em um budget alvo. A shrink_fn SHALL preservar a semântica do conteúdo (sumarizar, não truncar).

#### Scenario: Shrink de conversation
- **WHEN** a conversation tem 1500 tokens mas o budget disponível é 800
- **THEN** a shrink_fn sumariza mensagens antigas mantendo as 3 mais recentes, resultando em ≤800 tokens

#### Scenario: Shrink de lessons
- **WHEN** 10 lessons ocupam 2000 tokens mas o budget disponível é 500
- **THEN** a shrink_fn reduz para as 3 lessons mais relevantes, resultando em ≤500 tokens

### Requirement: Relatório de uso do budget
O `ContextBudget` SHALL expor um método `usage_report()` que retorna o consumo por tier e por componente. O relatório SHALL ser usado para logging e calibração.

#### Scenario: Relatório após build
- **WHEN** o prompt é montado via `build()`
- **THEN** `usage_report()` retorna um dicionário com tokens usados por tier e por componente nomeado
