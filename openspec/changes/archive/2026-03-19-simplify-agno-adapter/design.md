## Approach

Refatoração interna do `AgnoAdapter` para usar features nativas do Agno. Mudanças cirúrgicas em um único arquivo (`src/adapters/agno_adapter.py`). Nenhum arquivo externo é alterado.

## Architecture

Antes (atual):
```
AgnoAdapter
  ├─ _resolve_model()          # 30 linhas de if/elif
  ├─ _compress_prompt()        # 25 linhas cortando strings
  ├─ self._sessions dict       # vazio, não funciona
  ├─ Agent() recriado cada run # ineficiente
  ├─ asyncio.to_thread()       # workaround bloqueante
  └─ 11 wrapper functions      # 70 linhas de boilerplate
```

Depois (simplificado):
```
AgnoAdapter
  ├─ _normalize_model_id()     # 5 linhas: adiciona "provider:" se faltar
  ├─ self._agents_cache        # cache de Agent por agent_name
  ├─ self._db                  # SqliteDb compartilhado
  ├─ agent.arun()              # async nativo
  └─ _generate_tools()         # loop dinâmico sobre get_tool_definitions()
```

## Key Decisions

### D1: Normalização de model_id (não resolução)
Em vez de instanciar modelo por prefixo, apenas normalizar a string para o formato `provider:model_id` que o Agno aceita nativamente.

```python
def _normalize_model_id(model_id: str) -> str:
    """Adiciona prefixo de provider se não presente."""
    if ":" in model_id:
        return model_id  # já tem provider
    if model_id.startswith("gemini"):
        return f"google:{model_id}"
    if model_id.startswith(("gpt-", "o1-", "o3-")):
        return f"openai:{model_id}"
    if model_id.startswith("claude"):
        return f"anthropic:{model_id}"
    return f"google:{model_id}"  # fallback
```

### D2: Cache de agentes com invalidação por modelo
Dict `{agent_name: (Agent, model_id)}`. Se model_override difere do cacheado, cria agente temporário sem sobrescrever o cache.

```python
self._agents_cache: dict[str, tuple[Agent, str]] = {}

def _get_or_create_agent(self, agent_name, model_id, ...):
    cached = self._agents_cache.get(agent_name)
    if cached and cached[1] == model_id:
        return cached[0]
    agent = Agent(name=agent_name, model=model_id, ...)
    if not model_override:  # só cacheia se não for override temporário
        self._agents_cache[agent_name] = (agent, model_id)
    return agent
```

### D3: SqliteDb para sessions
Um único `SqliteDb` compartilhado por todos os agentes. O `session_id` é o `conversation_id` (demand_id). O arquivo fica em `{state_dir}/agno_sessions.db`.

```python
from agno.db.sqlite import SqliteDb

self._db = SqliteDb(db_file=f"{state_dir}/agno_sessions.db")

# Ao criar Agent:
agent = Agent(
    db=self._db,
    session_id=conversation_id,
    add_history_to_context=True,
    num_history_runs=5,
)
```

### D4: Geração dinâmica de tools
Itera sobre `get_tool_definitions()` e cria funções com assinatura tipada dinamicamente.

```python
def _generate_tools(self) -> list:
    tools = []
    for defn in self._mcp_server.get_tool_definitions():
        name = defn["name"]
        props = defn["inputSchema"].get("properties", {})
        required = defn["inputSchema"].get("required", [])

        # Cria função com closure capturando name
        async def tool_fn(_name=name, **kwargs) -> str:
            return await self._mcp_server.handle_tool_call(_name, kwargs)

        tool_fn.__name__ = name
        tool_fn.__doc__ = defn["description"]
        # Type hints para o Agno gerar o schema correto
        annotations = {p: str for p in props}
        annotations["return"] = str
        tool_fn.__annotations__ = annotations
        tools.append(tool_fn)
    return tools
```

### D5: Remover _compress_prompt, delegar pro Agno
Com `num_history_runs=5`, o Agno já limita o contexto. Se context_length_exceeded ocorrer, o retry reduz `num_history_runs` em vez de cortar linhas.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/adapters/agno_adapter.py` | MODIFY | Refatoração completa interna |
| `tests/adapters/test_agno_adapter.py` | MODIFY | Atualizar testes para nova estrutura |

## Risks

- **Geração dinâmica de tools**: O Agno precisa de type hints corretos para gerar o schema. Se a introspecção falhar, as tools não funcionam. Mitigação: testes específicos.
- **Cache de agentes**: Agente cacheado pode ficar stale se config mudar em runtime. Mitigação: invalidação por model_id + método `clear_cache()`.
- **Sessions SQLite**: Arquivo de DB pode crescer. Mitigação: state_dir já é limpo pelo engine em operações de manutenção.
