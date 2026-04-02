## ADDED Requirements

### Requirement: Restauração garantida do terminal via TerminalGuard
O sistema SHALL fornecer um context manager `TerminalGuard` que salva o estado do terminal ao entrar e restaura ao sair, independente do motivo da saída (erro, timeout, crash, SIGINT). O guard SHALL restaurar: termios settings (echo, canonical mode), file descriptors originais (stdout/stderr), e enviar escape sequences de cleanup (sair alternate screen, mostrar cursor, resetar cores).

#### Scenario: Crash do Textual restaura terminal
- **WHEN** o app Textual lança exceção não tratada durante `run_async()`
- **THEN** o `TerminalGuard.__exit__` restaura termios, fds e envia `\033[?1049l\033[?25h\033[0m` ao terminal original

#### Scenario: Timeout do adapter restaura terminal
- **WHEN** o adapter excede o timeout e o TUI é encerrado
- **THEN** o terminal retorna ao estado normal com echo de teclas e cursor visível

#### Scenario: SIGINT durante operação restaura terminal
- **WHEN** o usuário pressiona Ctrl+C durante qualquer operação
- **THEN** o terminal é restaurado antes do processo encerrar

### Requirement: Timeout em _wait_for_reply
O sistema SHALL aplicar timeout configurável (default 300s) em `_wait_for_reply()`. Quando o timeout expira, o Future pendente SHALL ser cancelado, uma mensagem de erro SHALL ser exibida no chat, e o input SHALL ser liberado para nova interação.

#### Scenario: Timeout ao aguardar resposta do engine
- **WHEN** `_wait_for_reply()` aguarda mais de 300 segundos sem resposta
- **THEN** o Future é cancelado, mensagem "Timeout — operação expirou" é exibida no chat, e o Squad Lead recebe notificação do erro

#### Scenario: Input liberado após timeout
- **WHEN** ocorre timeout em `_wait_for_reply()`
- **THEN** o indicador de typing é removido e o usuário pode digitar nova mensagem

### Requirement: Tasks supervisionadas com done_callback
O sistema SHALL registrar `done_callback` em toda task criada via `asyncio.create_task()` no TUI. O callback SHALL: remover a task do set de tasks ativas, verificar se houve exceção, e em caso de erro exibir mensagem no chat e limpar o indicador de typing.

#### Scenario: Exceção em callback de mensagem
- **WHEN** o `_message_callback` lança exceção durante processamento
- **THEN** o erro é exibido no chat com label "Erro", o indicador de typing é removido, e o input permanece funcional

#### Scenario: Task concluída com sucesso
- **WHEN** o `_message_callback` completa sem erros
- **THEN** a task é removida do set de tasks ativas sem efeitos colaterais

### Requirement: Redirecionamento de fds robusto
O sistema SHALL realizar o redirecionamento de stdout/stderr para log dentro do `TerminalGuard`, com rollback automático no `__exit__`. O fd original do terminal SHALL ser preservado via `os.dup()` antes de qualquer redirecionamento.

#### Scenario: Falha parcial no redirecionamento
- **WHEN** o redirecionamento de fd 2 falha após fd 1 já ter sido redirecionado
- **THEN** o `TerminalGuard.__exit__` restaura fd 1 ao original e o terminal não fica corrompido

### Requirement: Cancelamento de Futures no stop
O sistema SHALL cancelar qualquer `_pending_reply` Future ativo quando `stop()` é chamado, desbloqueando o event loop imediatamente.

#### Scenario: Stop com Future pendente
- **WHEN** `stop()` é chamado enquanto `_wait_for_reply()` aguarda resposta
- **THEN** o Future é cancelado, `_wait_for_reply` retorna via `CancelledError`, e o app encerra sem travar
