## Why

O AgnoAdapter reimplementa funcionalidades que o framework Agno já oferece nativamente — model resolution manual, sessions caseiras, compressão de prompt por corte de linhas, e 11 wrapper functions escritas à mão. Isso gera código desnecessário (~165 linhas), sessions que não funcionam (dict vazio), e não aproveita os recursos do framework. Simplificar reduz o adapter de ~517 para ~300 linhas e faz as features funcionarem de verdade.

## What Changes

- Eliminar `_resolve_model()` — usar sintaxe `model="provider:id"` nativa do Agno (v2.2.6+)
- Trocar `asyncio.to_thread(agent.run)` por `agent.arun()` async nativo
- Cache de agentes por `agent_name` — evitar recriação a cada chamada de `run()`
- Sessions nativas com `db=SqliteDb` + `session_id` — substituir o dict manual vazio
- Remover `_compress_prompt()` — delegar para `add_history_to_context` + `num_history_runs` do Agno
- Gerar function tools dinamicamente a partir de `get_tool_definitions()` — eliminar 11 wrappers manuais

## Capabilities

### New Capabilities
- `agno-native-features`: Uso de features nativas do Agno (model-as-string, arun, sessions com db, history management) no adapter

### Modified Capabilities
- `agno-adapter`: Simplificação interna mantendo a mesma interface pública `AIAgentAdapter`

## Impact

- **Código**: Apenas `src/adapters/agno_adapter.py` é modificado (~-165 linhas)
- **Interface**: Zero mudança — `AIAgentAdapter` intocada, engine intocado, Claude SDK intocado
- **Dependências**: Nenhuma nova (SqliteDb já vem com `agno`)
- **Testes**: Atualizar mocks para refletir nova estrutura interna
- **Compatibilidade**: 100% — comportamento externo idêntico
