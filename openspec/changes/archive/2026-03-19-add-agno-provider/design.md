## Approach

Criar `AgnoAdapter` como novo provider de IA no padrão existente — arquivo único em `src/adapters/agno_adapter.py` implementando `AIAgentAdapter`. As MCP tools do AI Squad são expostas ao Agno via MCP server stdio (reutilizando a mesma lógica de tools). O adapter é registrado na factory e selecionável via `ai_provider: agno`.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    PlatformFactory                        │
│  register_ai_adapter("agno", AgnoAdapter)                │
│  register_ai_adapter("claude-agent-sdk", ClaudeSDK...)   │
└──────────┬───────────────────────────┬───────────────────┘
           │                           │
    ┌──────▼──────┐           ┌───────▼────────┐
    │ AgnoAdapter │           │ ClaudeSDKAdapt │
    │ (novo)      │           │ (existente)    │
    └──────┬──────┘           └────────────────┘
           │
    ┌──────▼─────────────────────────────────────┐
    │           Agno Agent/Runner                 │
    │                                             │
    │  model: Gemini/OpenAI/Claude (nativo)       │
    │  tools:                                     │
    │    ├─ MCPTools (11 tools do AI Squad)        │
    │    ├─ DuckDuckGoTools (web search)           │
    │    ├─ PythonTools (code execution)           │
    │    └─ ShellTools (shell commands)            │
    │  skills:                                    │
    │    ├─ LocalSkills(agents/<name>/) SKILL.md  │
    │    ├─ LocalSkills(global-skills/)            │
    │    └─ fallback: AGENTS.md → instruction     │
    │  session: SessionService (persistência)     │
    └─────────────────────────────────────────────┘
```

## Key Decisions

### D1: MCP tools via servidor stdio interno
As 11 tools do AI Squad (start_agent, report_progress, etc.) são expostas ao Agno via MCP server stdio. O adapter cria um processo MCP server que encapsula os callbacks e o Agno consome via `MCPTools(transport="stdio", ...)`.

**Alternativa descartada**: Converter todas as tools para `FunctionTool` nativo do Agno. Isso duplicaria a lógica e quebraria a consistência com o adapter Claude.

**Decisão**: Criar um módulo `src/adapters/mcp_tools_server.py` que expõe os callbacks como MCP server standalone, reutilizável por qualquer adapter futuro.

### D2: Model mapping nativo (sem LiteLLM)
O Agno tem providers nativos para Gemini (`agno.models.google.Gemini`), OpenAI (`agno.models.openai.OpenAIChat`) e Claude (`agno.models.anthropic.Claude`). Usaremos os providers nativos.

**Mapeamento**:
```python
MODEL_MAP = {
    "gemini": "agno.models.google:Gemini",
    "gpt": "agno.models.openai:OpenAIChat",
    "claude": "agno.models.anthropic:Claude",
    "openai/": "agno.models.openai:OpenAIResponses",  # OpenAI Responses API
}
```

O adapter detecta o prefixo do model_id e instancia o provider correto.

### D3: Sessions via InMemorySessionService
Para manter simplicidade e paridade com o adapter Claude (que usa dict em memória), usaremos `InMemorySessionService` do Agno. Migração para `SqliteSessionService` pode ser feita depois sem alterar a interface.

### D4: Toolkits extras via config.yaml
O campo `tools` no config.yaml de cada agente mapeia diretamente para toolkits Agno:

```yaml
agents:
  dev:
    name: "Dev Backend"
    tools:
      - web_search        # → DuckDuckGoTools()
      - code_execution    # → PythonTools(base_dir="/tmp/sandbox")
      - shell             # → ShellTools(base_dir=working_dir)
```

O `AgentConfig` ganha um campo `tools: list[str]` e o adapter resolve os toolkits no momento da criação do agente.

### D5: MCP server de tools como módulo separado
O MCP server que expõe as 11 tools do AI Squad será extraído para `src/adapters/mcp_tools_server.py`. Isso permite:
- Reutilização: qualquer adapter futuro consome o mesmo server
- Testabilidade: server testável independentemente
- Desacoplamento: tools não dependem de nenhum adapter específico

O `ClaudeAgentSDKAdapter` continuará usando `create_sdk_mcp_server` (breaking change zero).

### D6: Prompt building reutilizado
O método `_build_prompt()` é idêntico entre adapters. Será extraído para uma função utilitária em `src/adapters/prompt_builder.py` para reutilização.

### D7: Skills com fallback AGENTS.md (Opção B)
O Agno tem sistema de Skills nativo (`SKILL.md` com frontmatter YAML + progressive discovery). Para manter compatibilidade com os presets existentes que usam `AGENTS.md`:

**Estratégia dual**:
- Se encontrar `SKILL.md` → usa `LocalSkills()` nativo (progressive discovery, lazy loading)
- Se encontrar apenas `AGENTS.md` → lê conteúdo e injeta como `instruction` do agente
- Se encontrar ambos → prioriza `SKILL.md`

```python
def _resolve_skills(self, agent_name: str) -> tuple[Skills | None, str]:
    """Retorna (skills_obj, instruction_fallback)."""
    loaders = []
    instruction_parts = []

    for dir_path in self._get_skill_dirs(agent_name):
        skill_md = dir_path / "SKILL.md"
        agents_md = dir_path / "AGENTS.md"

        if skill_md.exists():
            loaders.append(LocalSkills(str(dir_path)))
        elif agents_md.exists():
            instruction_parts.append(agents_md.read_text())

    skills = Skills(loaders=loaders) if loaders else None
    instruction = "\n\n".join(instruction_parts)
    return skills, instruction
```

**Vantagem**: Zero mudança nos presets existentes. Quem quiser progressive discovery cria `SKILL.md`. Quem não mudar nada continua funcionando via fallback.

## Data Flow

```
Usuário → Telegram → Engine → AgnoAdapter.run(prompt, context)
                                   │
                                   ├─ _build_prompt() → prompt completo
                                   ├─ _resolve_model(model_id) → Gemini/OpenAI/Claude
                                   ├─ _resolve_tools(agent_config) → [MCPTools, DDG, Python...]
                                   ├─ _resolve_skills(agent_name) → (Skills, instruction)
                                   ├─ _get_or_create_session(demand_id) → Session
                                   │
                                   ▼
                              Agno Runner.run_async()
                                   │
                                   ├─ Modelo raciocina e chama tools
                                   ├─ MCPTools → MCP server → callbacks do engine
                                   ├─ DuckDuckGoTools → web search
                                   ├─ PythonTools → executa código
                                   │
                                   ▼
                              Coleta resultado (async generator)
                                   │
                                   ▼
                              return texto final → Engine → Telegram → Usuário
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/adapters/agno_adapter.py` | CREATE | Implementação do AgnoAdapter |
| `src/adapters/mcp_tools_server.py` | CREATE | MCP server standalone com as 11 tools |
| `src/adapters/prompt_builder.py` | CREATE | Função utilitária de montagem de prompt |
| `src/factory.py` | MODIFY | Registrar AgnoAdapter na factory |
| `src/cli/templates/config.py` | MODIFY | Template com opção agno + campo tools |
| `pyproject.toml` | MODIFY | Adicionar dependência agno[google,tools] |
| `tests/adapters/test_agno_adapter.py` | CREATE | Testes do AgnoAdapter |
| `tests/adapters/test_mcp_tools_server.py` | CREATE | Testes do MCP server standalone |

## Dependencies

- `agno` (core framework)
- `agno[google]` (provider Gemini)
- `agno[tools]` (DuckDuckGoTools, PythonTools, ShellTools)
- `google-genai` (SDK Gemini, instalado via agno[google])

## Risks

- **Maturidade do Agno**: Framework com 38k stars e desenvolvimento ativo, mas menos battle-tested que o Claude SDK em produção
- **Compatibilidade de MCP**: O Agno consome MCP servers — precisamos garantir que o server stdio funcione corretamente com async
- **Model differences**: Gemini pode ter comportamento diferente do Claude com as mesmas instruções de prompt — pode exigir ajustes nas instruções do AGENTS.md por provider
