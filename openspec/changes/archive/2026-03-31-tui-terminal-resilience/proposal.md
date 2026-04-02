## Why

O TUI (`TUIMessageBus`) corrompe o terminal quando ocorre qualquer erro — timeout do adapter, exceção no callback, crash do Textual. O terminal fica em raw mode com caracteres estranhos, sem echo de teclas, e impossível de encerrar (nem Ctrl+C funciona). A causa raiz é a ausência total de cleanup/restauração do terminal no lifecycle do TUI.

## What Changes

- Introduzir `TerminalGuard` — context manager que salva/restaura estado do terminal (termios, fds, alternate screen) garantindo cleanup em qualquer cenário de saída
- Adicionar timeout configurável em `_wait_for_reply()` para evitar travamento infinito quando o engine não responde
- Supervisionar tasks de callback com `done_callback` para capturar exceções, limpar typing indicator e exibir erros no chat
- Tornar o redirecionamento de fds (stdout/stderr → log) robusto com rollback no `TerminalGuard`
- Garantir que `stop()` cancela Futures pendentes e que SIGINT/Ctrl+C sempre funciona

## Capabilities

### New Capabilities
- `tui-terminal-guard`: Gerenciamento robusto do ciclo de vida do terminal — salva/restaura termios, fds e escape sequences em qualquer cenário de saída (erro, timeout, crash, SIGINT)

### Modified Capabilities
- `messaging-bus`: Adicionar requisito de resiliência — implementações com controle de terminal SHALL restaurar o estado do terminal em qualquer cenário de saída (erro, shutdown, crash)

## Impact

- `src/messaging/tui.py` — redesign do `run_forever()`, `_wait_for_reply()`, `_on_user_input()` e `stop()`
- `src/messaging/interface.py` — possível adição de contrato de resiliência na docstring de `run_forever()`
- `tests/messaging/test_tui.py` — novos testes para timeout, cleanup de terminal, task supervision
- Sem breaking changes — a interface pública do `TUIMessageBus` não muda
