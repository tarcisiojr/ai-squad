# Design: TUI Messaging Bus

## Arquitetura

```
┌─────────────────────────────────────────────────┐
│                   Daemon                         │
│                                                  │
│  ┌──────────┐    callbacks     ┌──────────────┐ │
│  │  Engine   │◄───────────────►│ TUIMessageBus│ │
│  │          │  send_message    │              │ │
│  │          │  ask_user        │  ┌─────────┐ │ │
│  │          │  notify          │  │ Textual │ │ │
│  │          │                  │  │  App    │ │ │
│  └──────────┘                  │  └────┬────┘ │ │
│                                │       │      │ │
│                                └───────┼──────┘ │
└────────────────────────────────────────┼────────┘
                                         │
                                    ┌────▼────┐
                                    │ Terminal │
                                    └─────────┘
```

## Componentes

### 1. `TUIMessageBus` (src/messaging/tui.py)

Implementa `MessageBus` ABC. Ponto de integração entre o daemon e o Textual.

```python
class TUIMessageBus(MessageBus):
    def __init__(self, **kwargs):
        self._app = SquadTUIApp(bus=self)
        self._message_callback = None

    async def start(self):
        # Roda o app Textual como task async (não bloqueia)
        asyncio.create_task(self._app.run_async())

    async def send_message(self, user_id, text, *, thread_id=None, **kwargs):
        sender = kwargs.get("sender", "")
        self._app.append_message(sender or self._persona_label, text)

    async def ask_user(self, user_id, question, *, thread_id=None):
        return await self._app.prompt_user(question)

    async def send_approval_request(self, user_id, question, options, *, thread_id=None):
        return await self._app.prompt_approval(question, options)
```

### 2. `SquadTUIApp` (Textual App)

```
┌─ ai-squad · MeuTime ─────────────────────────────┐
│  ┌─ #chat ──────────────────────────────────────┐ │
│  │ (RichLog widget — scroll, markdown, wrap)    │ │
│  │                                              │ │
│  │ 👤 Você                                      │ │
│  │ Migrar módulo X                              │ │
│  │                                              │ │
│  │ 👨‍💼 Squad Lead                                │ │
│  │ Processando sua solicitação...               │ │
│  │                                              │ │
│  └──────────────────────────────────────────────┘ │
│  ┌─ Input ──────────────────────────────────────┐ │
│  │ > _                                          │ │
│  └──────────────────────────────────────────────┘ │
│  /help · /status · /quit · Ctrl+C                  │
└───────────────────────────────────────────────────┘
```

**Widgets:**
- `Header` — nome do time (Textual built-in)
- `RichLog` — painel de chat com scroll e rich text
- `Input` — campo de entrada (Textual built-in)
- `Footer` — atalhos (Textual built-in)

### 3. Fluxo de dados

```
Usuário digita texto
        │
        ▼
  Input.on_submit()
        │
        ▼
  TUIMessageBus._on_user_input(text)
        │
        ├─► Exibe "👤 Você: {text}" no RichLog
        │
        ▼
  self._message_callback(text)  ← daemon handler
        │
        ▼
  Engine processa (async)
        │
        ├─► report_progress → bus.send_message() → RichLog.write()
        │
        ▼
  Resposta final → bus.send_message() → RichLog.write()
```

### 4. Integração com asyncio

O Textual roda nativamente com asyncio. O `run_async()` integra o event loop do app com o do daemon. Mensagens do engine chegam via `call_from_thread` ou `post_message` do Textual para thread-safety.

### 5. Aprovações e perguntas

Para `ask_user()` e `send_approval_request()`:
- Exibe a pergunta/opções no RichLog
- Cria um `asyncio.Future`
- O próximo input do usuário resolve o Future
- Retorna o resultado ao engine

Mesmo pattern usado pelo GChatMessageBus (`_pending_text_reply`).

## Decisões

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Framework TUI | Textual | Async nativo, widgets ricos, Python puro |
| Layout v1 | Chat único + input | Escopo mínimo funcional |
| Thread support | Ignorado (v1) | Chat unificado, threads são futuro |
| Dependência | Optional extra `[tui]` | Não onera quem usa Telegram/GChat |
| Provider name | `tui` | Curto, claro, distinto de `cli` |
| Ativação | `--tui` flag OU `messaging_provider: tui` | Flexível |

## Arquivos

| Arquivo | Ação |
|---------|------|
| `src/messaging/tui.py` | Criar — TUIMessageBus + SquadTUIApp |
| `src/messaging/registry.py` | Editar — lazy import do tui |
| `src/cli/main.py` | Editar — flag `--tui` no comando start |
| `pyproject.toml` | Editar — extra `[tui]` com textual |
| `tests/messaging/test_tui.py` | Criar — testes unitários |
