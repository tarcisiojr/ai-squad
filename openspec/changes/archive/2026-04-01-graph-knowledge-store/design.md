## Context

O AI Squad possui 3 camadas de memória: LessonsStore (lições FTS5), KnowledgeStore (documentos Markdown com busca plugável) e memória operacional (journal, daily_notes, conversation). Todas armazenam fatos isolados sem conexões entre conceitos. O GraphStore adiciona uma camada relacional que conecta entidades extraídas via LLM, permitindo traversal de conhecimento.

O projeto já usa SQLite FTS5 em dois módulos (lessons.py, knowledge.py) com o mesmo padrão: init_db, lazy connection, atomic writes. O GraphStore segue esse padrão estabelecido.

## Goals / Non-Goals

**Goals:**
- Conectar conceitos entre demandas via grafo de entidades e relações em SQLite
- Extrair entidades e relações automaticamente via callback LLM (model_tier fast)
- Injetar contexto relacional nos prompts do Squad Lead e agentes
- Reforçar relações vistas repetidamente (peso acumulativo)
- Manter zero dependências externas novas

**Non-Goals:**
- Substituir LessonsStore ou KnowledgeStore — o grafo complementa, não substitui
- Busca semântica por embeddings — FTS5 é suficiente para localizar entidades por nome
- Visualização do grafo — fora do escopo desta change
- Grafo distribuído ou multi-tenancy — um graph.db por time é suficiente

## Decisions

### D1: SQLite com recursive CTEs para traversal
O traversal usa `WITH RECURSIVE` nativo do SQLite. Isso elimina dependência de graph DB externa (Neo4j, Kuzu) enquanto suporta navegação até profundidade 3 — suficiente para o caso de uso.

### D2: Extração via callback LLM (mesmo padrão do ConversationStore)
`GraphStore.set_extract_callback(fn)` recebe um async callable que o engine registra. O prompt de extração pede JSON estruturado com entidades e relações tipadas. Usa model_tier "fast" para minimizar custo.

### D3: Deduplicação por nome normalizado + tipo
Entidades são identificadas por `(lower(name), type)`. O prompt de extração recebe lista de entidades existentes para reutilizar nomes ao invés de criar duplicatas. Isso garante grafo conectado ao invés de ilhas isoladas.

### D4: Ingestão assíncrona em fire-and-forget
Ingestão é disparada como asyncio task — não bloqueia o fluxo principal. Falhas na extração são logadas mas não interrompem a operação. Throttle de 10s por demanda evita excesso de calls.

### D5: Pruning automático por idade e uso
Entidades com `mention_count=1` e idade > 30 dias são removidas. Relações com `weight <= 0` são removidas. Limites: MAX_ENTITIES=500, MAX_RELATIONS=2000. Pruning roda na ingestão quando limites são atingidos.

### D6: Reforço de peso nas relações
Quando uma relação já existente é extraída novamente, seu `weight` incrementa +1. Relações frequentes ganham destaque no prompt. Isso é o mecanismo central de "aprendizado" — o grafo fica mais confiante sobre relações vistas repetidamente.

### D7: FTS5 para busca inicial de entidades
Uma tabela virtual `entities_fts` indexa name e description. A consulta começa com FTS5 match, depois expande via traversal. Mesmo padrão do LessonsStore e KnowledgeStore.

### D8: Formato de prompt compacto
A saída de `format_for_prompt()` usa formato hierárquico: entidade principal → relações → entidades conectadas. Limite de MAX_CONTEXT_RESULTS=8 entidades para não sobrecarregar o prompt.

## Risks / Trade-offs

### R1: Qualidade da extração depende do LLM
Entidades e relações extraídas são tão boas quanto o LLM "fast" consegue produzir. Mitigação: validação de JSON estrita, tipos fechados (enum), e o reforço de peso naturalmente filtra ruído — relações incorretas não se repetem e eventualmente são podadas.

### R2: Custo de LLM por ingestão
Cada ingestão gera 1 call LLM. Com ~10 ingestões por demanda, isso adiciona ~10 calls "fast" por demanda. Mitigação: throttle de 10s, model_tier fast (haiku/flash), e batch de contexto quando possível.

### R3: Grafo pode ficar poluído com entidades genéricas
Termos como "erro", "bug", "código" podem aparecer como entidades sem valor. Mitigação: o prompt de extração instrui a ser específico, e o pruning remove entidades com baixo mention_count.

### R4: Recursive CTE com profundidade alta pode ser lento
Com 500 entidades e 2000 relações, profundidade 3 pode expandir muito. Mitigação: MAX_TRAVERSAL_DEPTH=3, LIMIT no resultado, e índices nas foreign keys.
