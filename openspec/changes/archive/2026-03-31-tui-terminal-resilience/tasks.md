## 1. TerminalGuard

- [x] 1.1 Criar classe `TerminalGuard` em `src/messaging/tui.py` com `__enter__`/`__exit__` — salva termios via `termios.tcgetattr()`, salva fds originais via `os.dup()`, restaura tudo no exit
- [x] 1.2 Implementar `redirect_fds(log_path)` no TerminalGuard — redireciona stdout/stderr para log, preserva fd do terminal para Textual
- [x] 1.3 Implementar cleanup de escape sequences no `__exit__` — envia `\033[?1049l\033[?25h\033[0m` ao fd original do terminal
- [x] 1.4 Refatorar `run_forever()` para usar `with TerminalGuard()` — mover toda a lógica de fd redirect para dentro do guard

## 2. Timeout e Cancelamento

- [x] 2.1 Refatorar `_wait_for_reply()` para usar `asyncio.wait_for()` com timeout de 300s — exibir mensagem de timeout no chat, limpar typing indicator, propagar TimeoutError
- [x] 2.2 Refatorar `stop()` para cancelar `_pending_reply` se ativo — garantir desbloqueio imediato do event loop

## 3. Tasks Supervisionadas

- [x] 3.1 Criar `_active_tasks: set[asyncio.Task]` e método `_create_supervised_task()` com `done_callback` — captura exceções, exibe erro no chat, limpa typing
- [x] 3.2 Substituir `asyncio.create_task()` em `_on_user_input()` por `_create_supervised_task()`
- [x] 3.3 Cancelar todas as tasks ativas no `stop()`

## 4. Docstring e Interface

- [x] 4.1 Atualizar docstring de `run_forever()` em `src/messaging/interface.py` — adicionar nota sobre restauração de terminal para providers com controle de terminal

## 5. Testes

- [x] 5.1 Teste: `TerminalGuard.__exit__` restaura termios e fds após exceção simulada
- [x] 5.2 Teste: `_wait_for_reply()` levanta `TimeoutError` após timeout e limpa typing
- [x] 5.3 Teste: `_on_task_done()` exibe erro no chat e limpa typing quando task falha
- [x] 5.4 Teste: `stop()` cancela `_pending_reply` pendente e tasks ativas
