# Tasks: Preset Helpdesk

## Fase 1: Knowledge Store (core)

- [x] Criar `src/orchestrator/knowledge.py` com ABC `KnowledgeBackend`
  - Métodos: `index(doc_path)`, `search(query, limit)`, `reindex_all()`
  - Dataclass `KnowledgeResult`: path, title, snippet, score, used_count
- [x] Implementar `FTS5Backend` em `knowledge.py`
  - SQLite FTS5 indexando título + conteúdo + tags
  - Leitura de frontmatter YAML (score, tags, created)
  - Boost por score: `rank * (1 + score * 0.1)`
  - Indexação incremental (hash de conteúdo para detectar mudanças)
- [x] Implementar `QmdBackend` em `knowledge.py` (opcional)
  - Wrapper sobre `qmd` CLI (subprocess)
  - Detecção automática: `shutil.which("qmd")`
  - Fallback para FTS5 se qmd não disponível
- [x] Criar `KnowledgeStore` como facade
  - Seleciona backend (FTS5 ou qmd) baseado em config/disponibilidade
  - Expõe `search()`, `index()`, `update_score(doc_path, delta)`
  - Gerencia leitura/escrita de frontmatter com score
- [x] Testes para KnowledgeStore
  - Busca FTS5 com e sem resultados
  - Boost de score no ranking
  - Indexação incremental
  - Frontmatter parsing e atualização

## Fase 2: Document Ingest

- [x] Criar `src/orchestrator/ingest.py`
  - Classe `DocumentIngest` com registry de converters por extensão
  - Método `ingest(file_path, category) → Path` retorna path do .md gerado
  - Geração de slug para nome do arquivo
  - Adição de frontmatter padrão (score: 0, created, source, original_filename)
- [x] Implementar converters
  - `.pdf` → pdfplumber (dependência opcional, try/except ImportError)
  - `.docx` → python-docx (dependência opcional)
  - `.md` → cópia direta + frontmatter se não existir
  - `.txt` → wrap em markdown com título inferido da primeira linha
  - `.jpg/.png` → placeholder (descrição será gerada pelo agente via LLM)
- [x] Testes para DocumentIngest
  - Conversão de cada formato
  - Geração de slug
  - Frontmatter adicionado corretamente
  - Handling de arquivo sem extensão / formato desconhecido

## Fase 3: Reaction Tracker + Telegram

- [x] Criar `src/orchestrator/reaction_tracker.py`
  - `ReactionTracker` com LRU dict (max 10k entries, TTL 24h)
  - Método `track(msg_id, doc_path)` — registra mapeamento
  - Método `on_reaction(msg_id, emoji)` — atualiza score via KnowledgeStore
  - Emojis: 👍 → +1, 👎 → -1 (mínimo 0)
- [x] Estender `src/messaging/telegram.py`
  - Adicionar handler `_handle_document` para arquivos genéricos (PDF, DOCX, etc.)
  - Adicionar handler `_handle_reaction` para `message_reaction` updates
  - Adicionar callbacks: `receive_document(callback)`, `on_reaction(callback)`
  - Retornar `message_id` do `_send()` para uso no tracking
- [x] Estender `src/messaging/interface.py`
  - Adicionar métodos opcionais: `receive_document()`, `on_reaction()`
  - Manter compatibilidade — CLIMessageBus ignora (no-op)
- [x] Testes para ReactionTracker
  - Track + reação positiva incrementa score
  - Reação sem mapeamento é ignorada
  - LRU expira entries antigas
  - Score não vai abaixo de 0

## Fase 4: Preset Helpdesk (pipeline + agentes)

- [x] Criar `src/presets/helpdesk/pipeline/pipeline.yaml`
  - Steps: atendimento (subagent, powerful), escalação (checkpoint), registro (inline, fast)
- [x] Criar `src/presets/helpdesk/pipeline/steps/step-01-atendimento.md`
  - Quality gate: resposta deve ser clara, baseada em doc se disponível
  - Veto: resposta que contradiz documentação da KB
- [x] Criar `src/presets/helpdesk/pipeline/steps/step-02-escalacao.md`
  - Checkpoint: pausa para humano
  - Condição: atendente não encontrou solução
- [x] Criar `src/presets/helpdesk/pipeline/steps/step-03-registro.md`
  - Quality gate: .md salvo com frontmatter correto, indexado
- [x] Criar `src/presets/helpdesk/agents/squad-lead/AGENTS.md`
  - Classificação: chamado vs ingestão vs status
  - Roteamento para atendente ou base-conhecimento
  - Gerenciamento de escalação
- [x] Criar `src/presets/helpdesk/agents/atendente/AGENTS.md`
  - Busca na KB via tool
  - Resposta baseada em contexto
  - Registro de soluções novas
  - Tracking de msg_id → doc para reações
- [x] Criar `src/presets/helpdesk/agents/base-conhecimento/AGENTS.md`
  - Recebe arquivos, converte, indexa, commita
  - Confirma ao usuário
- [x] Criar estrutura `src/presets/helpdesk/knowledge/`
  - Diretórios: atendimentos/, documentacao/sistemas/, documentacao/processos/, documentacao/faq/
  - .gitkeep em cada diretório

## Fase 5: Integração

- [x] Integrar KnowledgeStore no `prompt_builder.py`
  - Quando preset é helpdesk, busca contexto na KB antes de montar prompt do atendente
  - Injeta trechos relevantes como "## Documentos relevantes da base de conhecimento"
- [x] Integrar ReactionTracker no `engine.py`
  - Inicializa tracker quando preset helpdesk
  - Conecta callback de reação do Telegram ao tracker
  - Passa msg_id de volta ao tracker após envio de resposta
- [x] Integrar DocumentIngest no agente base-conhecimento
  - Disponibilizar como MCP tool ou via prompt instructions
  - Agente usa filesystem tools para converter e salvar
- [x] Registrar preset no CLI
  - `ai-squad create MeuSuporte --preset helpdesk`
  - Copia estrutura com knowledge/ vazio
- [x] Testes de integração
  - Fluxo completo: chamado → busca → resposta → reação → score
  - Fluxo ingestão: documento → conversão → indexação → commit
  - Escalação: chamado sem solução → checkpoint → humano → registro
