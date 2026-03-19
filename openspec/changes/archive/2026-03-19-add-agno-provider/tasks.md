## Tasks

### Task 1: Extrair prompt builder compartilhado
- [x] Criar `src/adapters/prompt_builder.py` com função `build_prompt(prompt: str, context: dict) → str`
- [x] Extrair lógica de `ClaudeAgentSDKAdapter._build_prompt()` para a função compartilhada
- [x] Atualizar `ClaudeAgentSDKAdapter` para usar `build_prompt()` do módulo compartilhado
- [x] Testes: verificar que o comportamento do prompt building não mudou

**Arquivos**: `src/adapters/prompt_builder.py` (CREATE), `src/adapters/claude_agent_sdk.py` (MODIFY)

### Task 2: Criar MCP tools server standalone
- [x] Criar `src/adapters/mcp_tools_server.py` com classe `SquadMCPToolsServer`
- [x] Encapsular as 11 tools (report_progress, start_agent, get_running_agents, get_demand_state, get_pipeline_state, advance_step, skip_step, rerun_step, read_journal, send_image, learn_lesson)
- [x] Cada tool recebe callback via construtor e delega para o callback do engine
- [x] Expor como MCP server stdio executável (`python -m src.adapters.mcp_tools_server`)
- [x] Testes unitários para cada tool com callbacks mockados

**Arquivos**: `src/adapters/mcp_tools_server.py` (CREATE), `tests/adapters/test_mcp_tools_server.py` (CREATE)

### Task 3: Adicionar campo tools ao AgentConfig
- [x] Adicionar campo `tools: list[str] = field(default_factory=list)` no `AgentConfig`
- [x] Parsear campo `tools` no `PlatformConfig.from_yaml()`
- [x] Adicionar campo opcional `web_search_provider: str = ""` no `AgentConfig`
- [x] Atualizar template de config em `src/cli/templates/config.py` com exemplos comentados
- [x] Testes: verificar parsing do campo tools do YAML

**Arquivos**: `src/factory.py` (MODIFY), `src/cli/templates/config.py` (MODIFY)

### Task 4: Implementar AgnoAdapter
- [x] Criar `src/adapters/agno_adapter.py` com classe `AgnoAdapter(AIAgentAdapter)`
- [x] Implementar `__init__` com parâmetros: timeout, working_dir, model, allowed_tools, agents_dir, global_skills_dir
- [x] Implementar `_resolve_model(model_id: str)` → instância Agno Model (Gemini/OpenAI/Claude)
- [x] Implementar `_resolve_tools(agent_config)` → lista de toolkits Agno baseado no campo tools
- [x] Implementar `_resolve_skills(agent_name)` → tuple(Skills | None, str) com fallback AGENTS.md:
  - Verificar 3 diretórios (agente, globais, projeto) em ordem
  - Se encontrar SKILL.md → adicionar `LocalSkills(dir)` ao loaders
  - Se encontrar apenas AGENTS.md → ler conteúdo e acumular em instruction
  - Se encontrar ambos → priorizar SKILL.md
  - Retornar `(Skills(loaders=...), instruction_fallback)`
- [x] Implementar `_get_or_create_session(conversation_id)` → Session via InMemorySessionService
- [x] Implementar `run(prompt, context) → str` usando Agno Runner.run_async()
  - Passar `skills=skills_obj` e `instruction=instruction_fallback` ao criar Agent
- [x] Implementar `ask(question) → str` delegando para run()
- [x] Implementar `status() → AgentStatus`
- [x] Implementar `on_human_needed(callback)`
- [x] Implementar todos os `set_*_callback()` (11 callbacks)
- [x] Implementar retry com backoff exponencial (2/4/8s) — reutilizar lógica do Claude adapter
- [x] Implementar compressão de prompt para context_length_exceeded — reutilizar `_compress_prompt`
- [x] Implementar model override temporário via context
- [x] Consumir MCP tools server via `MCPTools(transport="stdio", ...)`
- [x] Suportar imagem no prompt (campo image_path no context)

**Arquivos**: `src/adapters/agno_adapter.py` (CREATE)

### Task 5: Registrar AgnoAdapter na factory
- [x] Importar `AgnoAdapter` em `src/factory.py` ou no daemon
- [x] Registrar com `factory.register_ai_adapter("agno", AgnoAdapter)`
- [x] Garantir import condicional (só importa agno se provider = agno) para não quebrar instalações sem agno

**Arquivos**: `src/factory.py` (MODIFY) ou `src/daemon.py` (MODIFY)

### Task 6: Adicionar dependências ao pyproject.toml
- [x] Adicionar grupo de dependência opcional `[agno]` com: `agno`, `google-genai`
- [x] Documentar instalação: `pip install -e ".[agno]"`
- [x] Manter dependências do Claude SDK como estão (não quebrar nada)

**Arquivos**: `pyproject.toml` (MODIFY)

### Task 7: Testes do AgnoAdapter
- [x] Criar `tests/adapters/test_agno_adapter.py`
- [x] Testar instanciação com parâmetros padrão
- [x] Testar `_resolve_model` para Gemini, OpenAI, Claude
- [x] Testar `_resolve_tools` para cada toolkit (web_search, code_execution, shell)
- [x] Testar `_resolve_skills` com SKILL.md nativo (usa LocalSkills)
- [x] Testar `_resolve_skills` com AGENTS.md fallback (retorna instruction string)
- [x] Testar `_resolve_skills` com ambos (prioriza SKILL.md)
- [x] Testar `_resolve_skills` com diretório inexistente (ignora silenciosamente)
- [x] Testar `_resolve_skills` com 3 níveis de skills simultaneamente
- [x] Testar `run()` com mock do Agno Runner
- [x] Testar gerenciamento de sessions (criar, retomar, limpar)
- [x] Testar retry com backoff (mock de erros transientes)
- [x] Testar compressão de prompt
- [x] Testar model override temporário
- [x] Testar callbacks (todos os 11 set_*_callback)
- [x] Testar campo tools ignorado quando provider é claude-agent-sdk

**Arquivos**: `tests/adapters/test_agno_adapter.py` (CREATE)

### Task 8: Teste de integração adapter + engine
- [x] Testar fluxo completo: engine → AgnoAdapter → mock Agno → resultado
- [x] Verificar que MCP tools são chamadas corretamente pelo engine via adapter
- [x] Verificar que sessions são mantidas entre chamadas para mesma demanda
- [x] Verificar que model routing funciona (light_model vs heavy_model)

**Arquivos**: `tests/test_integration.py` (MODIFY)
