## MODIFIED Requirements

### Requirement: Prompt com contexto do produto
O AIAgentAdapter SHALL aceitar contexto do produto como parte do dicionário de contexto passado ao método `run`.

#### Scenario: Contexto do produto no build_prompt
- **WHEN** o context dict contém chave "product_context"
- **THEN** o adapter MUST incluir seção "## Contexto do Projeto" no prompt antes de "## Tarefa"

#### Scenario: Sem contexto do produto
- **WHEN** o context dict não contém "product_context"
- **THEN** o adapter MUST montar prompt normalmente sem seção de contexto do projeto
