# Tasks: TUI Messaging Bus

## Implementação

- [x] **T1: Dependência Textual** — Adicionar extra `[tui]` no `pyproject.toml` com `textual>=0.40`
- [x] **T2: TUIMessageBus + SquadTUIApp** — Criar `src/messaging/tui.py` com:
  - `TUIMessageBus` implementando `MessageBus` ABC
  - `SquadTUIApp` (Textual App) com Header, RichLog (chat), Input, Footer
  - Fluxo: Input → callback do daemon → resposta no RichLog
  - `ask_user()` e `send_approval_request()` com Future pattern
  - `notify()` com destaque visual
- [x] **T3: Registry** — Registrar provider `tui` com lazy import em `src/messaging/registry.py`
- [x] **T4: Flag --tui** — Adicionar `--tui` no comando `start` em `src/cli/main.py` (override de `messaging_provider`)
- [x] **T5: Testes** — Criar `tests/messaging/test_tui.py` com testes unitários (interface, send_message, callbacks)
- [x] **T6: Validação** — Testar fluxo completo: start com --tui, enviar mensagem, receber resposta do Squad Lead
