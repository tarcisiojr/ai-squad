## Why

A pasta `state/` cresce indefinidamente — cada demanda gera um `.json` de estado e uma subpasta com conversation, journal e pipeline-state. Após conclusão (`done`), esses arquivos nunca são removidos, apesar de o conhecimento útil já ter migrado para `lessons.db`, `graph.db` e `daily/`. O método `delete_state()` existe mas não é chamado por ninguém. Com o tempo, isso polui o diretório e aumenta o tempo de varredura do `get_all_demands()`.

## What Changes

- Registrar timestamp de conclusão (`done_at`) quando uma demanda muda para estado `done`
- Implementar rotina de cleanup que remove demandas concluídas há mais de 7 dias
- Remover tanto o `.json` de estado quanto a subpasta associada (conversation, journal, pipeline-state)
- Executar cleanup automaticamente no boot do daemon e no início de cada nova demanda
- Preservar `lessons.db`, `graph.db`, `daily/` e `squad-lead-session/` (conhecimento durável)

## Capabilities

### New Capabilities
- `state-cleanup`: Expurgo automático de demandas concluídas após TTL configurável (default 7 dias)

### Modified Capabilities
- `orchestrator`: O engine precisa acionar o cleanup nos momentos corretos (boot e nova demanda)

## Impact

- **Código**: `src/orchestrator/state.py` (cleanup + done_at), `src/orchestrator/engine.py` (trigger de cleanup), `src/daemon.py` (trigger no boot)
- **Dados**: Arquivos em `state/` serão removidos após 7 dias em estado `done` — irreversível mas seguro pois conhecimento já está em lessons/graph/daily
- **APIs**: Nenhuma mudança em interfaces públicas
- **Dependências**: Nenhuma nova dependência
