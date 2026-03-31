## Context

O `TUIMessageBus` usa Textual para renderizar chat interativo no terminal. O Textual ativa alternate screen + raw mode ao iniciar. Quando qualquer erro ocorre (timeout do adapter, exceção no callback, crash), o terminal fica corrompido porque não há cleanup. O `run_forever()` redireciona stdout/stderr para log file via manipulação de fds do OS, mas sem rollback em caso de falha.

Estado atual problemático:
- `_wait_for_reply()` bloqueia infinitamente sem timeout
- `asyncio.create_task()` fire-and-forget sem exception handler
- Nenhuma restauração de terminal no `finally` de `run_forever()`
- Ctrl+C depende do Textual processar eventos — se o loop está travado, não funciona

## Goals / Non-Goals

**Goals:**
- Terminal SEMPRE restaurado ao sair, independente do motivo
- Erros do engine/adapter exibidos no chat sem travar a interface
- Ctrl+C funciona em qualquer estado
- Input liberado após timeout (Squad Lead trata o erro)

**Non-Goals:**
- Mudar a experiência visual do TUI (layout, widgets, CSS)
- Suporte a retry automático no TUI (isso é responsabilidade do engine)
- Mudar a interface pública do `MessageBus` ABC

## Decisions

### D1: TerminalGuard como context manager

Criar classe `TerminalGuard` no próprio `tui.py` que encapsula todo o gerenciamento de terminal.

```python
class TerminalGuard:
    """Salva e restaura estado do terminal."""

    def __enter__(self):
        # Salva termios do stdin (se é TTY)
        # Salva fds originais via os.dup()
        return self

    def __exit__(self, *exc):
        # Restaura fds
        # Restaura termios
        # Envia escape sequences de cleanup
        # Fecha arquivos temporários

    def redirect_fds(self, log_path: str | None):
        # Redireciona stdout/stderr para log
        # Remove StreamHandlers dos loggers
```

**Alternativa considerada**: Usar `atexit.register()` para cleanup. Descartado porque `atexit` não executa em SIGKILL e não tem acesso ao contexto de fds salvos.

**Alternativa considerada**: Mover fd redirect para o daemon. Descartado porque o redirect é específico do TUI — outros providers não precisam.

### D2: Timeout via asyncio.wait_for

```python
async def _wait_for_reply(self, timeout: float = 300.0) -> str:
    self._pending_reply = asyncio.get_event_loop().create_future()
    try:
        return await asyncio.wait_for(self._pending_reply, timeout=timeout)
    except asyncio.TimeoutError:
        if self._app:
            self._app.set_typing(None)
            self._app.append_chat("⏰ Timeout", "Operação expirou após aguardar resposta.")
        raise  # Propaga para o engine tratar
    except asyncio.CancelledError:
        raise  # stop() cancelou — propagar para encerrar
    finally:
        self._pending_reply = None
```

O timeout propaga `TimeoutError` para o engine/Squad Lead, que já tem lógica de retry. O TUI apenas limpa o indicador de typing e exibe mensagem.

**Alternativa considerada**: Retornar string de erro em vez de propagar exceção. Descartado porque o engine precisa saber que foi timeout para decidir retry vs abort.

### D3: Tasks supervisionadas com set de tracking

```python
self._active_tasks: set[asyncio.Task] = set()

def _create_supervised_task(self, coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    self._active_tasks.add(task)
    task.add_done_callback(self._on_task_done)
    return task

def _on_task_done(self, task: asyncio.Task) -> None:
    self._active_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Erro em task do TUI: %s", exc)
        if self._app:
            self._app.set_typing(None)
            self._app.append_chat("❌ Erro", str(exc))
```

No `stop()`, cancela todas as tasks ativas antes de encerrar.

### D4: Escape sequences de cleanup no TerminalGuard

Sequências enviadas no `__exit__` ao fd original do terminal:
- `\033[?1049l` — sai do alternate screen buffer
- `\033[?25h` — mostra cursor
- `\033[0m` — reseta atributos (cores, bold, etc.)

Essas sequências são seguras mesmo se o terminal já está no estado normal (são idempotentes).

### D5: stop() cancela Futures pendentes

```python
async def stop(self) -> None:
    # Cancela Future pendente (desbloqueia _wait_for_reply)
    if self._pending_reply and not self._pending_reply.done():
        self._pending_reply.cancel()

    # Cancela tasks ativas
    for task in self._active_tasks:
        task.cancel()

    # Encerra Textual
    if self._app and self._app.is_running:
        self._app.exit()
```

## Risks / Trade-offs

- **[termios indisponível no Windows]** → `TerminalGuard` verifica `hasattr(termios)` e degrada graciosamente. Na prática, Textual já não suporta Windows sem Windows Terminal, então risco é baixo.
- **[Timeout interrompe operação legítima longa]** → 300s é generoso. Se precisar de mais, o engine pode re-enviar a pergunta. Futuramente pode ser configurável via `config.yaml`.
- **[Escape sequences podem conflitar com multiplexadores]** → tmux/screen tratam essas sequences corretamente. Testado com os mais comuns.

## Arquivos Afetados

| Arquivo | Ação |
|---------|------|
| `src/messaging/tui.py` | Redesign — adicionar `TerminalGuard`, refatorar `run_forever()`, `_wait_for_reply()`, `_on_user_input()`, `stop()` |
| `src/messaging/interface.py` | Editar — adicionar nota de resiliência na docstring de `run_forever()` |
| `tests/messaging/test_tui.py` | Expandir — testes para timeout, cleanup, task supervision |
