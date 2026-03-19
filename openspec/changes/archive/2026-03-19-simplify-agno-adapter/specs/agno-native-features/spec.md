# agno-native-features

## Purpose

Substituir implementações manuais no AgnoAdapter por features nativas do framework Agno, reduzindo código e melhorando funcionalidade (sessions que funcionam, history management real, async nativo).

## Requirements

### Requirement: Model como string nativa
O adapter SHALL passar o model_id diretamente ao Agno usando a sintaxe `"provider:model_id"`. O adapter SHALL normalizar model_ids que não tenham prefixo de provider, adicionando o prefixo correto baseado no padrão do id (gemini→google, gpt/o1/o3→openai, claude→anthropic).

#### Scenario: Model id com prefixo (passthrough)
- **WHEN** config.yaml tem `ai_model: google:gemini-2.0-flash`
- **THEN** o adapter passa `model="google:gemini-2.0-flash"` direto ao Agent

#### Scenario: Model id sem prefixo (normalização)
- **WHEN** config.yaml tem `ai_model: gemini-2.0-flash`
- **THEN** o adapter normaliza para `"google:gemini-2.0-flash"` e passa ao Agent

#### Scenario: Model override com prefixo
- **WHEN** context tem `model_override: openai:gpt-4o`
- **THEN** o adapter usa `model="openai:gpt-4o"` para essa execução

### Requirement: Execução async nativa
O adapter SHALL usar `agent.arun(prompt)` em vez de `asyncio.to_thread(agent.run, prompt)`. Isto elimina overhead de thread pool e usa o event loop corretamente.

#### Scenario: Execução async
- **WHEN** `run()` é chamado
- **THEN** o adapter executa `await agent.arun(prompt)` diretamente no event loop

### Requirement: Cache de agentes por nome
O adapter SHALL manter cache de instâncias Agent por `agent_name`. O agente SHALL ser criado na primeira chamada e reutilizado nas seguintes. O cache SHALL ser invalidado quando o model muda (model_override diferente do cached).

#### Scenario: Primeira execução cria agente
- **WHEN** `run()` é chamado com agent_name="po" pela primeira vez
- **THEN** o adapter cria o Agent e armazena no cache

#### Scenario: Execuções seguintes reutilizam
- **WHEN** `run()` é chamado com agent_name="po" novamente
- **THEN** o adapter reutiliza o Agent do cache sem recriar

#### Scenario: Model override invalida cache
- **WHEN** `run()` é chamado com agent_name="po" e model_override diferente do modelo cacheado
- **THEN** o adapter cria novo Agent com o modelo override (sem sobrescrever o cache)

### Requirement: Sessions nativas com persistência
O adapter SHALL usar `db=SqliteDb(db_file=...)` e `session_id=conversation_id` do Agno para persistência de sessões. O adapter SHALL eliminar o `self._sessions` dict manual. O arquivo de db SHALL ficar no state_dir do time.

#### Scenario: Conversa com session_id
- **WHEN** `run()` é chamado com demand_id="criar-api-1234"
- **THEN** o Agent é executado com `session_id="criar-api-1234"` e histórico é persistido no SQLite

#### Scenario: Retomada de sessão
- **WHEN** `run()` é chamado com demand_id que já tem sessão no SQLite
- **THEN** o Agent retoma a conversa com histórico anterior

### Requirement: History management nativo
O adapter SHALL usar `add_history_to_context=True` e `num_history_runs=5` para gerenciamento de contexto. Isto substitui o `_compress_prompt()` manual. O adapter SHALL remover o método `_compress_prompt()`.

#### Scenario: Contexto com histórico limitado
- **WHEN** o agente tem 20 runs na sessão
- **THEN** apenas as últimas 5 são incluídas no contexto (num_history_runs=5)

### Requirement: Function tools geradas dinamicamente
O adapter SHALL gerar as 11 function tools automaticamente a partir de `SquadMCPToolsServer.get_tool_definitions()`, em vez de declará-las manualmente. Cada tool gerada SHALL ter nome, docstring e type hints derivados da definição.

#### Scenario: Todas as tools disponíveis
- **WHEN** o Agent é criado
- **THEN** as 11 tools são geradas automaticamente e disponíveis para o modelo chamar

#### Scenario: Nova tool adicionada ao server
- **WHEN** uma nova tool é adicionada ao `SquadMCPToolsServer.get_tool_definitions()`
- **THEN** ela é automaticamente disponibilizada no Agent sem alterar o AgnoAdapter

### Requirement: Compatibilidade com ClaudeSDKAdapter
Todas as mudanças SHALL ser internas ao `AgnoAdapter`. O `ClaudeAgentSDKAdapter`, a interface `AIAgentAdapter`, o engine e todos os módulos do orchestrator SHALL permanecer intocados.

#### Scenario: Suite de testes completa
- **WHEN** todas as simplificações são aplicadas
- **THEN** os 590+ testes existentes continuam passando sem modificação
