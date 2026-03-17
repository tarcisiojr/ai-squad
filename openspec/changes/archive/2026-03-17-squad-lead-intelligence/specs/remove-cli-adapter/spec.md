# Spec: Remover ClaudeCodeCLIAdapter

## Objetivo
Remover o adapter legado `claude --print` (subprocess single-shot) já que o Claude Agent SDK é o adapter principal e oferece capacidades superiores.

## O que é removido

| Arquivo | Ação |
|---------|------|
| `src/adapters/claude_code.py` | Deletar |
| `build/lib/src/adapters/claude_code.py` | Deletar |
| `tests/` referências ao ClaudeCodeCLIAdapter | Remover/atualizar |
| `src/factory.py` registro do adapter `claude-code` | Remover |

## O que permanece

| Arquivo | Status |
|---------|--------|
| `src/adapters/interface.py` | Mantido (ABC) |
| `src/adapters/claude_agent_sdk.py` | Mantido (adapter principal) |

## Impacto na configuração

`platform.yaml` passa a ter apenas uma opção de ai_provider:

```yaml
# Antes
ai_provider: claude-code  # ou claude-agent-sdk

# Depois
ai_provider: claude-agent-sdk  # único provider
```

## Justificativa

O ClaudeCodeCLIAdapter (`claude --print`) é single-shot sem tool use. O ClaudeAgentSDKAdapter já suporta:
- Multi-turn com agent loop (30+ turns)
- MCP tools nativas
- Sessões persistentes com resume
- Skills por agente
- Subagentes nativos
- Read, Edit, Bash, Grep, Glob via Claude Code

Manter o adapter legado é código morto que confunde e não oferece vantagem.

## Critérios de Aceite

- [ ] `src/adapters/claude_code.py` removido
- [ ] Factory não registra mais o provider `claude-code`
- [ ] `platform.yaml` usa `claude-agent-sdk` como provider
- [ ] Todos os testes passam usando apenas o SDK adapter
- [ ] Nenhuma importação residual do ClaudeCodeCLIAdapter no codebase
