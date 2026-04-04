"""Implementação TUI (Terminal User Interface) do barramento de mensageria.

Usa Textual para renderizar chat interativo no terminal com personas,
aprovações e integração assíncrona com o daemon.
"""

import asyncio
import logging
import os
import sys
from typing import Callable

from ai_squad.messaging.interface import MessageBus
from ai_squad.messaging.registry import register

logger = logging.getLogger("ai-squad.tui")

# Identificador do usuário local
LOCAL_USER = "local"

# Timeout padrão para aguardar resposta do usuário (segundos)
_REPLY_TIMEOUT = 300.0

# Escape sequences para restaurar terminal
_RESET_SEQUENCES = (
    "\033[?1049l"  # sai do alternate screen buffer
    "\033[?25h"  # mostra cursor
    "\033[0m"  # reseta atributos (cores, bold, etc.)
)


class TerminalGuard:
    """Context manager que salva e restaura estado do terminal.

    Garante que o terminal volte ao estado normal independente do motivo
    da saída — erro, timeout, crash ou SIGINT.
    """

    def __init__(self) -> None:
        self._saved_termios: list | None = None
        self._saved_fd1: int | None = None
        self._saved_fd2: int | None = None
        self._tty_fd: int | None = None
        self._tty_file = None
        self._saved_stdout = None
        self._saved_stderr = None
        self._saved_dunder_stderr = None
        self._devnull_file = None
        self._stdin_is_tty = False

    def __enter__(self) -> "TerminalGuard":
        # Salva termios do stdin (se é TTY)
        try:
            import termios

            if sys.stdin.isatty():
                self._saved_termios = termios.tcgetattr(sys.stdin.fileno())
                self._stdin_is_tty = True
        except (ImportError, OSError):
            pass

        # Salva fds originais de stdout/stderr
        try:
            self._saved_fd1 = os.dup(1)
            self._saved_fd2 = os.dup(2)
        except OSError as e:
            logger.warning("Falha ao salvar fds originais: %s", e)

        # Salva wrappers Python
        self._saved_stdout = sys.stdout
        self._saved_stderr = sys.stderr
        self._saved_dunder_stderr = sys.__stderr__

        return self

    def redirect_fds(self, log_path: str | None) -> None:
        """Redireciona stdout/stderr para log e preserva terminal para Textual."""
        # Preserva fd do terminal para Textual
        try:
            self._tty_fd = os.dup(2)
            self._tty_file = os.fdopen(self._tty_fd, "w", closefd=False)
        except OSError as e:
            logger.warning("Falha ao preservar fd do terminal: %s", e)
            return

        # Redireciona fd 1/2 do OS para log file
        try:
            if log_path:
                _log_fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
            else:
                _log_fd = os.open(os.devnull, os.O_WRONLY)
            os.dup2(_log_fd, 1)
            os.dup2(_log_fd, 2)
            os.close(_log_fd)
        except OSError as e:
            logger.warning("Falha ao redirecionar fds: %s", e)
            return

        # Preserva terminal para Textual via sys.__stderr__
        sys.__stderr__ = self._tty_file  # type: ignore[assignment]

        # Redireciona wrappers Python para devnull
        self._devnull_file = open(os.devnull, "w")  # noqa: SIM115
        sys.stdout = self._devnull_file
        sys.stderr = self._devnull_file

        # Remove StreamHandlers de todos os loggers
        self._remove_stream_handlers()

    def _remove_stream_handlers(self) -> None:
        """Remove StreamHandlers (não FileHandler) de todos os loggers."""
        import logging as _logging

        root = _logging.getLogger()
        for handler in root.handlers[:]:
            if isinstance(handler, _logging.StreamHandler) and not isinstance(
                handler, _logging.FileHandler
            ):
                root.removeHandler(handler)
        for name in list(_logging.Logger.manager.loggerDict):
            named_logger = _logging.getLogger(name)
            for handler in named_logger.handlers[:]:
                if isinstance(handler, _logging.StreamHandler) and not isinstance(
                    handler, _logging.FileHandler
                ):
                    named_logger.removeHandler(handler)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        # Restaura fds originais
        try:
            if self._saved_fd1 is not None:
                os.dup2(self._saved_fd1, 1)
                os.close(self._saved_fd1)
                self._saved_fd1 = None
            if self._saved_fd2 is not None:
                os.dup2(self._saved_fd2, 2)
                os.close(self._saved_fd2)
                self._saved_fd2 = None
        except OSError as e:
            # Último recurso: tenta escrever no tty_fd
            self._emergency_log(f"Falha ao restaurar fds: {e}")

        # Restaura wrappers Python
        if self._saved_stdout is not None:
            sys.stdout = self._saved_stdout
        if self._saved_stderr is not None:
            sys.stderr = self._saved_stderr
        if self._saved_dunder_stderr is not None:
            sys.__stderr__ = self._saved_dunder_stderr  # type: ignore[assignment]

        # Restaura termios (echo, canonical mode)
        if self._saved_termios is not None:
            try:
                import termios

                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved_termios)
            except (ImportError, OSError) as e:
                self._emergency_log(f"Falha ao restaurar termios: {e}")

        # Envia escape sequences de cleanup ao terminal
        try:
            target = sys.stderr if sys.stderr.isatty() else sys.__stderr__
            if target and hasattr(target, "write"):
                target.write(_RESET_SEQUENCES)
                target.flush()
        except Exception:
            # Último recurso: tenta no fd 2 diretamente
            try:
                os.write(2, _RESET_SEQUENCES.encode())
            except OSError:
                pass

        # Fecha arquivos temporários
        if self._devnull_file:
            try:
                self._devnull_file.close()
            except Exception:
                pass
        if self._tty_file:
            try:
                self._tty_file.close()
            except Exception:
                pass

    def _emergency_log(self, msg: str) -> None:
        """Log de emergência quando os loggers normais podem não funcionar."""
        try:
            if self._tty_file:
                self._tty_file.write(f"[TUI Guard] {msg}\n")
                self._tty_file.flush()
        except Exception:
            pass


class TUIMessageBus(MessageBus):
    """Barramento de mensageria via TUI (Textual).

    Renderiza chat interativo no terminal com suporte a personas,
    aprovações e input assíncrono.

    O Textual é o dono principal do terminal — roda via run_forever(),
    não como task em background, garantindo controle total de stdin/stdout.
    TerminalGuard garante restauração do terminal em qualquer cenário de saída.
    """

    def __init__(self, **kwargs) -> None:
        self._persona_name = kwargs.get("persona_name", "ai-squad")
        self._persona_avatar = kwargs.get("persona_avatar", "🤖")
        self._team_name = self._persona_name
        self._message_callback: Callable | None = None
        self._voice_callback: Callable | None = None
        self._app: "SquadTUIApp | None" = None
        # Future para aguardar respostas de texto (ask_user/approval)
        self._pending_reply: asyncio.Future | None = None
        # Personas registradas para exibir no painel
        self._personas: dict = {}
        # Status de trabalho de cada agente (key -> label ou "")
        self._agent_working: dict[str, str] = {}
        # Tasks ativas supervisionadas
        self._active_tasks: set[asyncio.Task] = set()

    # --- Ciclo de vida ---

    async def start(self) -> None:
        """Prepara o app Textual (não inicia — run_forever faz isso)."""
        try:
            from textual.app import App  # noqa: F401
        except ImportError:
            raise ImportError(
                "textual é necessário para o provider TUI. Instale com: pip install textual"
            )

        self._app = SquadTUIApp(bus=self)
        logger.info("TUI preparada — será iniciada via run_forever()")

    async def run_forever(self) -> str:
        """Loop principal — roda o Textual como dono do terminal.

        Retorna string (não None) para indicar ao daemon que este método
        é o loop principal e não precisa de shutdown_event.wait().

        Usa TerminalGuard para garantir restauração do terminal em qualquer
        cenário de saída (erro, timeout, crash, SIGINT).

        Não faz redirecionamento de fds do OS — Textual precisa de acesso
        direto ao terminal para detectar tamanho e renderizar fullscreen.
        """
        if not self._app:
            return "no_app"

        with TerminalGuard():
            try:
                await self._app.run_async()
            except Exception as e:
                logger.error("Erro no app TUI: %s", e)

        return "tui_exited"

    async def stop(self) -> None:
        """Para o app Textual, cancelando operações pendentes."""
        # Cancela Future pendente (desbloqueia _wait_for_reply)
        if self._pending_reply and not self._pending_reply.done():
            self._pending_reply.cancel()

        # Cancela tasks ativas
        for task in self._active_tasks.copy():
            task.cancel()
        self._active_tasks.clear()

        # Encerra Textual
        if self._app and self._app.is_running:
            self._app.exit()
        logger.info("TUI parada")

    # --- Auto-descrição ---

    @classmethod
    def required_env_vars(cls) -> list[str]:
        """TUI não precisa de variáveis de ambiente."""
        return []

    @classmethod
    def env_template(cls) -> str:
        """TUI não precisa de template de .env."""
        return ""

    # --- Capacidades ---

    @property
    def default_chat_id(self) -> str:
        """Retorna identificador local."""
        return LOCAL_USER

    # --- Registro de personas ---

    def register_personas(self, personas: dict) -> None:
        """Registra personas para exibir na barra de status."""
        self._personas = personas

    # --- Comunicação ---

    async def send_message(
        self, user_id: str, text: str, *, thread_id: str | None = None, **kwargs: str
    ) -> None:
        """Exibe mensagem no chat TUI."""
        sender = kwargs.pop("sender", "")
        label = sender or f"{self._persona_avatar} {self._persona_name}"
        agent_key = self._find_agent_key(sender)

        if self._app:
            # Feedback periódico ("Trabalhando...") não polui o chat
            if agent_key and text.startswith("Trabalhando..."):
                self._app.set_typing(None)
                return

            self._app.set_typing(None)
            self._app.append_chat(label, text)
            self._app.refocus_input()

    async def send_approval_request(
        self,
        user_id: str,
        question: str,
        options: list[str],
        *,
        thread_id: str | None = None,
    ) -> str:
        """Exibe opções numeradas e aguarda resposta do usuário."""
        text_options = "\n".join(f"  {i + 1}. {opt}" for i, opt in enumerate(options))
        prompt_text = f"{question}\n\n{text_options}\n\nDigite o número da opção:"
        label = f"{self._persona_avatar} {self._persona_name}"

        if self._app:
            self._app.set_typing(None)
            self._app.append_chat(label, prompt_text)

        resposta = await self._wait_for_reply()

        try:
            indice = int(resposta.strip()) - 1
            if 0 <= indice < len(options):
                return options[indice]
        except ValueError:
            pass
        return resposta

    async def ask_user(self, user_id: str, question: str, *, thread_id: str | None = None) -> str:
        """Exibe pergunta e aguarda resposta de texto livre."""
        label = f"{self._persona_avatar} {self._persona_name}"
        if self._app:
            self._app.set_typing(None)
            self._app.append_chat(label, question)

        return await self._wait_for_reply()

    async def receive_message(self, callback: Callable) -> None:
        """Registra callback para mensagens de texto."""
        self._message_callback = callback

    async def receive_voice(self, callback: Callable) -> None:
        """Registra callback para voz (não suportado na TUI — no-op)."""
        self._voice_callback = callback

    async def notify(self, user_id: str, text: str, *, thread_id: str | None = None) -> None:
        """Exibe notificação no chat TUI."""
        if self._app:
            self._app.append_chat("🔔 Notificação", text)

    async def send_typing(self, user_id: str, *, thread_id: str | None = None) -> None:
        """Mostra indicador de 'trabalhando' no painel de agentes."""
        if self._app:
            self._app.set_typing("Processando...")

    def _find_agent_key(self, sender: str) -> str | None:
        """Encontra a key do agente pelo nome/avatar no sender label."""
        if not sender:
            return None
        for key, persona in self._personas.items():
            if key == "squad-lead":
                continue
            avatar = getattr(persona, "avatar", "")
            name = getattr(persona, "name", key)
            if avatar in sender and name in sender:
                return key
        return None

    # --- Controle de status de agentes ---

    def mark_agent_active(self, agent_label: str) -> None:
        """Ativa spinner do agente na barra de status."""
        agent_key = self._find_agent_key(agent_label)
        if agent_key:
            self._agent_working[agent_key] = "Trabalhando..."

    def mark_agent_idle(self, agent_label: str) -> None:
        """Desativa spinner do agente na barra de status."""
        agent_key = self._find_agent_key(agent_label)
        if agent_key:
            self._agent_working[agent_key] = ""

    # --- Internals ---

    async def _wait_for_reply(self, timeout: float = _REPLY_TIMEOUT) -> str:
        """Aguarda o próximo input do usuário como resposta.

        Aplica timeout para evitar travamento infinito. Em caso de timeout,
        exibe mensagem no chat e propaga TimeoutError para o engine tratar.
        """
        self._pending_reply = asyncio.get_event_loop().create_future()
        try:
            return await asyncio.wait_for(self._pending_reply, timeout=timeout)
        except asyncio.TimeoutError:
            if self._app:
                self._app.set_typing(None)
                self._app.append_chat(
                    "⏰ Timeout",
                    "Operação expirou após aguardar resposta.",
                )
            raise
        except asyncio.CancelledError:
            # stop() cancelou o Future — propagar para encerrar
            raise
        finally:
            self._pending_reply = None

    def _create_supervised_task(self, coro) -> asyncio.Task:  # noqa: ANN001
        """Cria task com supervisão — captura exceções e limpa estado."""
        task = asyncio.create_task(coro)
        self._active_tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return task

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Callback executado quando uma task supervisionada termina."""
        self._active_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("Erro em task do TUI: %s", exc)
            if self._app:
                self._app.set_typing(None)
                self._app.append_chat("❌ Erro", str(exc))

    async def _on_user_input(self, text: str) -> None:
        """Chamado pelo app Textual quando o usuário envia texto."""
        if self._app:
            self._app.append_chat("👤 Você", text)

        # Se há uma pergunta pendente, resolve o Future
        if self._pending_reply and not self._pending_reply.done():
            self._pending_reply.set_result(text)
            return

        # Caso contrário, envia para o daemon como nova mensagem
        if self._message_callback:
            try:
                if self._app:
                    self._app.set_typing("Processando...")
                self._create_supervised_task(self._message_callback(text, user_id=LOCAL_USER))
            except Exception as e:
                logger.error("Erro ao processar input: %s", e)
                if self._app:
                    self._app.set_typing(None)
                    self._app.append_chat("❌ Erro", str(e))


# --- App Textual ---


class SquadTUIApp:
    """App TUI para o ai-squad usando Textual.

    Importa Textual internamente para não falhar quando não instalado.
    """

    def __init__(self, bus: TUIMessageBus) -> None:
        self._bus = bus
        self._inner_app = None

    @property
    def is_running(self) -> bool:
        """Verifica se o app está rodando."""
        return self._inner_app is not None and self._inner_app.is_running

    def exit(self) -> None:
        """Encerra o app Textual."""
        if self._inner_app:
            self._inner_app.exit()

    def append_chat(self, sender: str, text: str) -> None:
        """Adiciona mensagem ao chat de forma segura."""
        if not self._inner_app or not self._inner_app.is_running:
            return
        try:
            self._inner_app.do_append_chat(sender, text)
        except Exception as e:
            logger.warning("Falha ao adicionar mensagem ao chat: %s", e)

    def refocus_input(self) -> None:
        """Recoloca foco no input."""
        if not self._inner_app or not self._inner_app.is_running:
            return
        try:
            self._inner_app.do_refocus_input()
        except Exception:
            pass

    def set_typing(self, label: str | None) -> None:
        """Atualiza painel de agentes."""
        if not self._inner_app or not self._inner_app.is_running:
            return
        try:
            self._inner_app.do_set_typing(label)
        except Exception:
            pass

    async def run_async(self) -> None:
        """Inicia o app Textual — este é o loop principal do terminal."""
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal
        from textual.widgets import Input, RichLog, Static

        bus = self._bus

        # Frames do spinner braille dots
        _SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

        class _InnerTUIApp(App):
            """App Textual interno — design minimalista."""

            ENABLE_COMMAND_PALETTE = False
            _spinner_tick: int = 0

            CSS = """
            Screen {
                background: #000000;
            }
            #chat {
                height: 1fr;
                padding: 0 1;
                scrollbar-size: 1 1;
                background: #000000;
            }
            #status-line {
                height: 1;
                color: $text-muted;
                padding: 0 1;
                background: #000000;
            }
            #input-row {
                height: auto;
                max-height: 5;
                padding: 0 1;
                background: #000000;
            }
            #input-prompt {
                width: 3;
                height: 1;
                color: $accent;
            }
            #input-box {
                width: 1fr;
                border: none;
                background: #000000;
            }
            #input-box:focus {
                border: none;
            }
            """

            TITLE = f"ai-squad ({bus._team_name})"
            BINDINGS = [
                Binding("ctrl+c", "quit", "Sair", show=False),
                Binding("pageup", "scroll_up", show=False),
                Binding("pagedown", "scroll_down", show=False),
            ]

            def compose(self) -> ComposeResult:
                yield RichLog(id="chat", wrap=True, highlight=True, markup=True)
                yield Static(self._build_status_line(), id="status-line")
                with Horizontal(id="input-row"):
                    yield Static("❯ ", id="input-prompt")
                    yield Input(id="input-box", placeholder="Digite sua mensagem...")

            def _build_status_line(self) -> str:
                """Monta status line com agentes e spinner animado para quem está trabalhando."""
                personas = bus._personas
                if not personas:
                    return ""
                frame = _SPINNER_FRAMES[self._spinner_tick % len(_SPINNER_FRAMES)]
                parts: list[str] = []
                for key, persona in personas.items():
                    if key == "squad-lead":
                        continue
                    name = getattr(persona, "name", key)
                    status = bus._agent_working.get(key, "")
                    if status:
                        parts.append(f"[bold cyan]{name}[/bold cyan] [cyan]{frame}[/cyan]")
                    else:
                        parts.append(f"[dim]{name}[/dim]")
                return " · ".join(parts)

            def on_mount(self) -> None:
                self.query_one("#input-box", Input).focus()
                chat = self.query_one("#chat", RichLog)
                team = bus._team_name
                chat.write(f"[bold]ai-squad[/bold] [dim]({team})[/dim]")
                chat.write("[dim]PageUp/Down para rolar · /quit para sair[/dim]\n")
                # Anima spinner da status line a cada 100ms
                self.set_interval(0.1, self._advance_spinner)

            def _advance_spinner(self) -> None:
                """Avança frame do spinner e atualiza status line se há agente trabalhando."""
                has_working = any(v for v in bus._agent_working.values())
                if not has_working:
                    return
                self._spinner_tick += 1
                try:
                    status = self.query_one("#status-line", Static)
                    status.update(self._build_status_line())
                except Exception:
                    pass

            async def on_input_submitted(self, event: Input.Submitted) -> None:
                text = event.value.strip()
                if not text:
                    return
                event.input.clear()
                if text.lower() in ("/quit", "/exit"):
                    self.exit()
                    return
                await bus._on_user_input(text)

            def action_scroll_up(self) -> None:
                self.query_one("#chat", RichLog).scroll_up(animate=False)

            def action_scroll_down(self) -> None:
                self.query_one("#chat", RichLog).scroll_down(animate=False)

            def do_append_chat(self, sender: str, text: str) -> None:
                chat = self.query_one("#chat", RichLog)
                chat.write(f"\n[bold]{sender}[/bold]")
                chat.write(text)

            def do_refocus_input(self) -> None:
                self.query_one("#input-box", Input).focus()

            def do_set_typing(self, label: str | None) -> None:
                """Atualiza status line com estado dos agentes."""
                try:
                    status = self.query_one("#status-line", Static)
                    status.update(self._build_status_line())
                except Exception:
                    pass

        self._inner_app = _InnerTUIApp()
        await self._inner_app.run_async()


# Auto-registro no registry
register("tui", TUIMessageBus)
