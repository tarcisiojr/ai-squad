## Context

O ai-dev-team roda em Docker, escuta Telegram, e orquestra agentes PO/Dev/QA via Claude Agent SDK. A UX atual tem problemas críticos: botões inapropriados durante conversas, formatação quebrada, nomes hardcoded, Dev que não executa de fato, e fluxo linear que não segue o framework OpenSpec.

## Goals / Non-Goals

**Goals:**
- Conversa fluida com PO sem botões desnecessários
- Dev executa código de verdade (commits, branches)
- Fluxo OpenSpec: proposal → specs → design → implementação → validação
- PO pode pesquisar na internet
- Tudo configurável via config.yaml (zero hardcoded)
- Formatação legível no Telegram

**Non-Goals:**
- Interface web
- Múltiplos LLMs simultâneos
- Paralelismo de agentes (v1 é sequencial)

## Decisions

### 1. Dois modos de conversa: CHAT e APPROVAL

**Escolha**: O engine opera em dois modos com base num marcador no texto do agente.

**Modo CHAT** (padrão): agente responde → engine envia como mensagem normal → espera texto do usuário → envia de volta ao agente. Sem botões.

**Modo APPROVAL**: agente inclui marcador (`---SPEC_READY---`, `---DONE---`) → engine detecta, remove o marcador, e mostra a mensagem com botões [Aprovar] [Rejeitar].

```
Agente responde sem marcador → modo CHAT
  ┌──────────────┐         ┌──────────────┐
  │  PO: "Qual   │────────▶│  Telegram:   │
  │  estilo?"    │         │  texto puro   │
  └──────────────┘         └──────┬───────┘
                                  │
                           ┌──────▼───────┐
                           │  Usuário     │
                           │  digita      │
                           └──────┬───────┘
                                  │
                           ┌──────▼───────┐
                           │  Engine      │
                           │  reenvia     │
                           │  ao agente   │
                           └──────────────┘

Agente responde com marcador → modo APPROVAL
  ┌──────────────┐         ┌──────────────┐
  │  PO: "Spec   │────────▶│  Telegram:   │
  │  pronta..."  │         │  texto +     │
  │ SPEC_READY   │         │  [Aprovar]   │
  └──────────────┘         │  [Rejeitar]  │
                           └──────────────┘
```

**Marcadores por agente** (configurável no AGENTS.md):
- PO: `---SPEC_READY---`
- Dev: `---DONE---`
- QA: `---QA_DONE---`

**Razão**: Simples, o LLM controla o fluxo. Funciona como tool_use — o modelo segue convenções quando instruído.

### 2. Fluxo OpenSpec para demandas

**Escolha**: O ciclo de demanda segue o framework OpenSpec.

```
1. PO conversa com usuário (modo CHAT)
2. PO gera proposal.md → salva em specs/<demand-id>/proposal.md
3. Usuário aprova proposal (modo APPROVAL)
4. Dev lê proposal, implementa código no workspace
5. Dev faz commits, cria branch, gera design.md
6. Dev marca ---DONE--- → usuário aprova
7. QA lê specs + código, roda testes, valida
8. QA marca ---QA_DONE--- → demanda concluída
```

**Razão**: Alinhado com o que já fazemos manualmente com OpenSpec. Os artefatos ficam no repo como documentação.

### 3. Comandos dinâmicos da config

**Escolha**: Os comandos `/<agente>` são gerados a partir de `config.yaml`:

```yaml
personas:
  po:
    name: "PO Agent"
    avatar: "📋"
    command: "/po"
  dev-orchestrator:
    name: "Dev Agent"
    avatar: "🔧"
    command: "/dev"
  qa:
    name: "QA Agent"
    avatar: "🧪"
    command: "/qa"
```

O daemon lê `personas` e monta o dict de comandos dinamicamente. O `AGENT_LABELS` no engine também é construído a partir da config.

**Razão**: Zero hardcoded. Adicionar novo agente = editar config.yaml.

### 4. Texto plano no Telegram

**Escolha**: Remover todo `parse_mode="Markdown"`. Enviar tudo como texto plano.

**Alternativa**: Usar HTML parse_mode (mais permissivo que Markdown).

**Razão**: Texto plano nunca falha. O conteúdo vem do LLM e pode conter qualquer caractere. HTML seria uma opção futura se quisermos negrito/itálico, mas texto plano resolve o problema imediato.

### 5. Web search para PO via tools do SDK

**Escolha**: Configurar o Claude Agent SDK com `allowed_tools` incluindo busca web quando o agente é PO.

**Alternativas**: MCP server separado, API de busca externa

**Razão**: O SDK já suporta tools nativamente. Basta habilitar no `ClaudeAgentOptions`.

### 6. Dev com timeout estendido e feedback

**Escolha**: Timeout do Dev = 600s (10 min). A cada 30s sem resposta, o daemon envia "Dev trabalhando..." no Telegram.

**Razão**: O Dev pode estar gerando código, rodando testes, fazendo commits — tudo demora. Feedback evita que o usuário pense que travou.

## Risks / Trade-offs

**[LLM esquece o marcador]** → Mitigação: instruções claras e repetidas no AGENTS.md. Se após 5 turnos sem marcador, o engine pergunta ao usuário se quer finalizar.

**[Web search consome tokens]** → Mitigação: instruir PO a pesquisar só quando não tem informação suficiente no contexto do projeto.

**[Dev demora e não produz nada]** → Mitigação: após timeout, o engine verifica se houve mudanças no workspace (git status). Se não, notifica erro.

**[Texto plano menos visual]** → Mitigação: usar separadores (---), bullets (-), e indentação para organizar. Funcional > bonito.
