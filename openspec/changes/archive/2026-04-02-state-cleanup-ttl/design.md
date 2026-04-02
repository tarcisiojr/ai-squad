## Context

A pasta `state/` acumula arquivos indefinidamente. Cada demanda gera um `{demand_id}.json` e uma subpasta `{demand_id}/` com conversation, journal e pipeline-state. O método `delete_state()` já existe no `StateManager` mas nunca é chamado. O conhecimento útil já é persistido em `lessons.db`, `graph.db` e `daily/` durante a execução da demanda.

## Goals / Non-Goals

**Goals:**
- Remover automaticamente demandas concluídas após 7 dias
- Manter a pasta `state/` limpa sem intervenção manual
- Preservar todo conhecimento durável (lessons, graph, daily)

**Non-Goals:**
- Archival (mover para subpasta) — complexidade desnecessária, dados já estão em lessons/graph
- Limpeza de `daily/` — já tem janela de 3 dias no prompt, custo de armazenamento negligenciável
- Configuração via config.yaml — TTL hardcoded com default sensato, parametrizável via código

## Decisions

### 1. Timestamp `done_at` no JSON existente

Adicionar campo `done_at` (ISO 8601 UTC) ao JSON da demanda quando estado muda para `done`. Alteração cirúrgica no `set_state()`.

**Alternativa descartada**: Usar mtime do arquivo — frágil, qualquer read-write reescrita altera o mtime.

### 2. Método `cleanup_expired()` no StateManager

Implementar no próprio `StateManager` que já conhece a estrutura de `state/`. Varre `*.json`, filtra `state == "done"` com `done_at` expirado, remove `.json` + subpasta.

**Alternativa descartada**: Classe separada `StateCleaner` — overengineering para ~30 linhas de código.

### 3. Trigger no boot + nova demanda

Executar cleanup em dois pontos:
- **Boot do daemon** (`daemon.py`): limpa acúmulo de dias sem execução
- **Nova demanda** (`engine.py`): mantém limpo durante operação contínua

O cleanup é síncrono e rápido (glob + json.load + unlink). Não justifica async ou background task.

**Alternativa descartada**: Cron/scheduler interno — adiciona complexidade sem benefício para operação de ms.

### 4. Retrocompatibilidade com demandas legado

Demandas `done` sem `done_at` (criadas antes desta mudança) são ignoradas pelo cleanup. Elas serão expurgadas naturalmente quando o sistema for reiniciado após 7 dias de uso com a nova versão, ou podem ser limpas manualmente.

## Risks / Trade-offs

- **[Dados irrecuperáveis]** → Aceito: conhecimento já está em lessons/graph/daily. Se debug forense for necessário, o usuário pode aumentar TTL.
- **[Demandas legado sem done_at]** → Ignoradas silenciosamente. Log de warning na primeira varredura para visibilidade.
- **[Race condition]** → Negligenciável: cleanup roda no início do processamento, antes de qualquer agente. Mesmo se coincidisse, o pior caso é falha no unlink que é ignorada.
