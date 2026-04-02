## ADDED Requirements

### Requirement: Persistência de entidades e relações em SQLite
O GraphStore SHALL persistir entidades e relações em tabelas SQLite (`entities`, `relations`) com escrita atômica. Entidades SHALL ser identificadas pelo par `(name_normalized, type)`. Tipos de entidade permitidos: bug, pattern, module, technology, decision, agent, concept, artifact, quality. Tipos de relação permitidos: caused_by, resolved_by, affects, uses, produced, depends_on, related_to, rejected_by, improved_by.

#### Scenario: Entidade nova é persistida
- **WHEN** uma entidade com name="auth-middleware" e type="module" é adicionada
- **THEN** o GraphStore persiste a entidade com mention_count=1, first_seen e last_seen iguais ao timestamp atual

#### Scenario: Entidade duplicada incrementa mention_count
- **WHEN** uma entidade com mesmo name_normalized e type já existe no grafo
- **THEN** o GraphStore incrementa mention_count e atualiza last_seen sem criar duplicata

#### Scenario: Relação é persistida com peso
- **WHEN** uma relação from="auth-middleware" to="session-timeout" type="affects" é adicionada
- **THEN** o GraphStore persiste a relação com weight=1, demand_id e evidence

### Requirement: Extração de entidades e relações via callback LLM
O GraphStore SHALL extrair entidades e relações de texto via callback LLM assíncrono registrado por `set_extract_callback(fn)`. O prompt de extração SHALL incluir a lista de entidades existentes para deduplicação. A extração SHALL retornar JSON estruturado validado contra tipos permitidos.

#### Scenario: Ingestão de texto gera entidades e relações
- **WHEN** `ingest(text, demand_id)` é chamado com texto descrevendo "Bug no login causado por timeout no auth-middleware"
- **THEN** o GraphStore invoca o callback LLM, parseia o JSON retornado, e persiste entidades (login, auth-middleware, timeout) e relações (timeout caused_by auth-middleware)

#### Scenario: Callback LLM não registrado
- **WHEN** `ingest()` é chamado sem callback registrado
- **THEN** o GraphStore loga warning e retorna sem erro

#### Scenario: Callback LLM retorna JSON inválido
- **WHEN** o callback LLM retorna texto que não é JSON válido ou não segue o schema esperado
- **THEN** o GraphStore loga warning e descarta a extração sem erro

#### Scenario: Entidades existentes são passadas no prompt
- **WHEN** o grafo já contém entidades ["auth-middleware", "jwt-library"]
- **THEN** o prompt de extração inclui essas entidades para que o LLM reutilize nomes existentes

### Requirement: Traversal via recursive CTE
O GraphStore SHALL navegar relações a partir de uma entidade usando recursive CTE do SQLite. A profundidade máxima de traversal SHALL ser configurável com default de 3 níveis.

#### Scenario: Traversal encontra entidades conectadas
- **WHEN** `traverse("auth-middleware", depth=2)` é chamado e existem relações auth-middleware→session-timeout→dev-backend
- **THEN** o GraphStore retorna as 3 entidades com suas relações e profundidade

#### Scenario: Traversal respeita limite de profundidade
- **WHEN** `traverse("A", depth=1)` é chamado e existem relações A→B→C→D
- **THEN** o GraphStore retorna apenas A e B, não C e D

#### Scenario: Traversal com entidade inexistente
- **WHEN** `traverse("entidade-que-nao-existe")` é chamado
- **THEN** o GraphStore retorna lista vazia

### Requirement: Busca por FTS5 com expansão por traversal
O GraphStore SHALL buscar entidades via FTS5 (name + description) e expandir resultados via traversal. O método `query(text, limit)` SHALL combinar FTS5 match com navegação de relações.

#### Scenario: Busca textual encontra entidades e expande relações
- **WHEN** `query("problemas com autenticação")` é chamado
- **THEN** o GraphStore encontra entidades matching via FTS5 e expande cada uma com traversal depth=2, retornando entidades e relações conectadas

#### Scenario: Busca sem resultados
- **WHEN** `query("termo sem match")` é chamado
- **THEN** o GraphStore retorna lista vazia

### Requirement: Reforço de peso nas relações
O GraphStore SHALL incrementar o weight de relações já existentes quando a mesma relação (from, to, type) é extraída novamente. O peso SHALL influenciar a ordenação dos resultados no prompt.

#### Scenario: Relação vista duas vezes tem peso reforçado
- **WHEN** a relação auth-middleware→session-timeout (type=affects) é extraída em duas demandas diferentes
- **THEN** o weight da relação é 2 e ela aparece com maior destaque no prompt

#### Scenario: Reforço explícito via reinforce
- **WHEN** `reinforce("auth-middleware", "session-timeout", delta=1)` é chamado
- **THEN** o weight da relação incrementa em 1

### Requirement: Pruning automático
O GraphStore SHALL remover entidades e relações antigas/pouco usadas quando limites são atingidos. Limites: MAX_ENTITIES=500, MAX_RELATIONS=2000. Entidades com mention_count=1 e idade > 30 dias SHALL ser removidas. Relações com weight <= 0 SHALL ser removidas.

#### Scenario: Entidade antiga e pouco usada é removida
- **WHEN** o grafo atinge MAX_ENTITIES e existe uma entidade com mention_count=1 e first_seen > 30 dias atrás
- **THEN** o GraphStore remove a entidade e suas relações associadas

#### Scenario: Relação com peso zero é removida
- **WHEN** uma relação tem weight <= 0
- **THEN** o GraphStore remove a relação durante pruning

### Requirement: Formatação para prompt
O GraphStore SHALL formatar resultados de consulta em texto Markdown compacto para injeção no prompt dos agentes. O limite SHALL ser MAX_CONTEXT_RESULTS=8 entidades. O formato SHALL mostrar entidade principal, suas relações e entidades conectadas.

#### Scenario: Formatação hierárquica
- **WHEN** `format_for_prompt("autenticação")` é chamado e existem resultados
- **THEN** o GraphStore retorna texto Markdown com entidades, relações tipadas e pesos

#### Scenario: Sem resultados retorna string vazia
- **WHEN** `format_for_prompt("termo sem match")` é chamado
- **THEN** o GraphStore retorna string vazia

### Requirement: Ingestão assíncrona não bloqueante
A ingestão SHALL ser executada como asyncio task fire-and-forget. Falhas na extração SHALL ser logadas mas não SHALL interromper o fluxo principal. Throttle de no mínimo 10 segundos entre ingestões da mesma demanda SHALL ser respeitado.

#### Scenario: Ingestão não bloqueia fluxo principal
- **WHEN** `ingest(text, demand_id)` é chamado
- **THEN** a extração roda em background e o método retorna imediatamente

#### Scenario: Throttle entre ingestões
- **WHEN** duas ingestões para a mesma demand_id são disparadas com intervalo < 10s
- **THEN** a segunda ingestão é descartada silenciosamente

#### Scenario: Falha na extração não interrompe operação
- **WHEN** o callback LLM falha com exceção
- **THEN** o GraphStore loga o erro e continua operando normalmente
