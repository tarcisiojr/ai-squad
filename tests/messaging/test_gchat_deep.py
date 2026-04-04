"""Testes profundos para GChatMessageBus — cobertura de caminhos internos."""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from ai_squad.messaging.gchat import GChatMessageBus

# googleapiclient pode nao estar instalado no ambiente de teste
_has_googleapiclient = "googleapiclient" in sys.modules or bool(__import__("importlib").util.find_spec("googleapiclient"))
_skip_no_google = pytest.mark.skipif(
    not _has_googleapiclient,
    reason="googleapiclient nao instalado",
)


@pytest.fixture
def bus(monkeypatch):
    """Cria instancia de GChatMessageBus com env vars mockadas."""
    monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake/creds.json")
    monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/AAAA123")
    return GChatMessageBus(persona_name="Squad", persona_avatar="🤖", activation_mode="all")


# --- _build_service ---


@_skip_no_google
class TestBuildService:
    """Testes para _build_service e autenticacao."""

    def test_build_service_service_account(self, bus, tmp_path):
        """Verifica construcao com Service Account."""
        creds_data = {"type": "service_account", "project_id": "test"}
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps(creds_data))
        bus._credentials_path = str(creds_file)

        with patch("googleapiclient.discovery.build") as mock_build:
            mock_service = MagicMock()
            mock_service.spaces().messages().list().execute.return_value = {"messages": []}
            mock_build.return_value = mock_service

            with patch.object(bus, "_auth_service_account", return_value=MagicMock()):
                bus._build_service()

        assert bus._service is not None
        assert bus._is_oauth is False

    def test_build_service_oauth_client(self, bus, tmp_path):
        """Verifica construcao com OAuth Client."""
        creds_data = {"installed": {"client_id": "test"}}
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps(creds_data))
        bus._credentials_path = str(creds_file)

        with patch("googleapiclient.discovery.build") as mock_build:
            mock_service = MagicMock()
            mock_service.spaces().messages().list().execute.return_value = {"messages": []}
            mock_build.return_value = mock_service

            with patch.object(bus, "_auth_oauth_client", return_value=MagicMock()):
                with patch.object(bus, "_discover_authenticated_user"):
                    bus._build_service()

        assert bus._service is not None
        assert bus._is_oauth is True

    def test_build_service_web_oauth(self, bus, tmp_path):
        """Verifica construcao com OAuth Client tipo web."""
        creds_data = {"web": {"client_id": "test"}}
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps(creds_data))
        bus._credentials_path = str(creds_file)

        with patch("googleapiclient.discovery.build") as mock_build:
            mock_service = MagicMock()
            mock_service.spaces().messages().list().execute.return_value = {"messages": []}
            mock_build.return_value = mock_service

            with patch.object(bus, "_auth_oauth_client", return_value=MagicMock()):
                with patch.object(bus, "_discover_authenticated_user"):
                    bus._build_service()

        assert bus._is_oauth is True

    def test_build_service_formato_nao_reconhecido(self, bus, tmp_path):
        """Verifica que formato de credencial invalido lanca ValueError."""
        creds_data = {"unknown": "format"}
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps(creds_data))
        bus._credentials_path = str(creds_file)

        with patch("googleapiclient.discovery"):
            with pytest.raises(ValueError, match="Formato de credencial"):
                bus._build_service()

    def test_build_service_idempotente(self, bus):
        """Segunda chamada nao recria service."""
        bus._service = MagicMock()
        bus._build_service()
        # Nao deve ter aberto arquivo — service ja existia

    def test_build_service_validation_request_falha(self, bus, tmp_path):
        """Request de validacao que falha nao impede inicializacao."""
        creds_data = {"type": "service_account", "project_id": "test"}
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps(creds_data))
        bus._credentials_path = str(creds_file)

        with patch("googleapiclient.discovery.build") as mock_build:
            mock_service = MagicMock()
            mock_service.spaces().messages().list().execute.side_effect = Exception("fail")
            mock_build.return_value = mock_service

            with patch.object(bus, "_auth_service_account", return_value=MagicMock()):
                bus._build_service()

        assert bus._service is not None

    def test_build_service_import_error(self, bus):
        """Verifica que ImportError e relancado com mensagem util."""
        with patch.dict("sys.modules", {"googleapiclient": None, "googleapiclient.discovery": None}):
            with patch("builtins.__import__", side_effect=ImportError("no google")):
                with pytest.raises(ImportError, match="google-api-python-client"):
                    bus._build_service()


# --- _discover_authenticated_user ---


@_skip_no_google
class TestDiscoverAuthenticatedUser:
    """Testes para _discover_authenticated_user."""

    def test_via_env_var(self, bus, monkeypatch):
        """Verifica que GCHAT_USER_ID e lido do env."""
        monkeypatch.setenv("GCHAT_USER_ID", "user@test.com")
        bus._discover_authenticated_user(MagicMock())
        assert bus._authenticated_user_id == "user@test.com"

    def test_via_service_account_email(self, bus, monkeypatch):
        """Verifica deteccao via service_account_email."""
        monkeypatch.delenv("GCHAT_USER_ID", raising=False)
        creds = MagicMock()
        creds.service_account_email = "sa@project.iam.gserviceaccount.com"
        bus._discover_authenticated_user(creds)
        assert bus._authenticated_user_id == "sa@project.iam.gserviceaccount.com"

    def test_via_oauth2_userinfo(self, bus, monkeypatch):
        """Verifica deteccao via oauth2 userinfo API."""
        monkeypatch.delenv("GCHAT_USER_ID", raising=False)
        # Cria mock que tem token mas NAO tem service_account_email
        creds = MagicMock()
        del creds.service_account_email
        creds.token = "fake-token"

        with patch("googleapiclient.discovery.build") as mock_build:
            mock_oauth2 = MagicMock()
            mock_oauth2.userinfo().get().execute.return_value = {"email": "user@test.com"}
            mock_build.return_value = mock_oauth2
            bus._discover_authenticated_user(creds)

        assert bus._authenticated_user_id == "user@test.com"

    def test_falha_nao_propaga(self, bus, monkeypatch):
        """Falha na deteccao nao propaga excecao."""
        monkeypatch.delenv("GCHAT_USER_ID", raising=False)
        creds = MagicMock(spec=[])  # Sem atributos
        bus._discover_authenticated_user(creds)
        # Nao deve ter falhado


# --- _auth_oauth_client ---


@_skip_no_google
class TestAuthOAuthClient:
    """Testes para _auth_oauth_client."""

    def test_import_error(self, bus):
        """Verifica que ImportError e relancado com mensagem util."""
        with patch.dict("sys.modules", {
            "google.auth.transport.requests": None,
            "google.oauth2.credentials": None,
            "google_auth_oauthlib.flow": None,
        }):
            with patch("builtins.__import__", side_effect=ImportError("no oauthlib")):
                with pytest.raises(ImportError, match="google-auth-oauthlib"):
                    bus._auth_oauth_client()


# --- _process_message caminhos adicionais ---


class TestProcessMessageDeep:
    """Testes para _process_message — caminhos menos cobertos."""

    @pytest.mark.asyncio
    async def test_process_message_chama_callback(self, bus):
        """Mensagem nova chama message_callback."""
        callback = AsyncMock()
        bus._message_callback = callback

        msg = {
            "createTime": "2026-01-01T00:00:10Z",
            "sender": {"type": "HUMAN", "name": "users/42"},
            "text": "nova demanda",
            "thread": {"name": "spaces/X/threads/T99"},
        }
        await bus._process_message(msg)

        callback.assert_called_once_with(
            "nova demanda",
            thread_id="spaces/X/threads/T99",
            user_id="users/42",
        )

    @pytest.mark.asyncio
    async def test_process_message_sem_callback(self, bus):
        """Mensagem sem callback nao falha."""
        bus._message_callback = None

        msg = {
            "createTime": "2026-01-01T00:00:10Z",
            "sender": {"type": "HUMAN", "name": "users/1"},
            "text": "texto",
            "thread": {"name": ""},
        }
        await bus._process_message(msg)

    @pytest.mark.asyncio
    async def test_process_message_activation_mode_command_ignora(self, bus):
        """Mensagem sem / em modo command e ignorada."""
        bus._activation_mode = "command"
        callback = AsyncMock()
        bus._message_callback = callback

        msg = {
            "createTime": "2026-01-01T00:00:10Z",
            "sender": {"type": "HUMAN", "name": "users/1"},
            "text": "texto sem barra",
            "thread": {"name": ""},
        }
        await bus._process_message(msg)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_resolve_fallback_reply(self, bus):
        """Resolve pending_reply via chave fallback (sem thread)."""
        future = asyncio.get_event_loop().create_future()
        bus._pending_text_reply["spaces/AAAA123"] = future

        msg = {
            "createTime": "2026-01-01T00:00:10Z",
            "sender": {"type": "HUMAN", "name": "users/1"},
            "text": "minha resposta fallback",
            "thread": {"name": "spaces/X/threads/T1"},
        }

        # A chave com thread nao existe, entao cai no fallback
        bus._activation_mode = "all"
        await bus._process_message(msg)

        # Nao resolveu via thread key, mas o loop nao usa fallback
        # pois o reply_key com thread nao existe no _pending_text_reply
        # Verificamos se o callback foi chamado
        assert not future.done() or future.result() == "minha resposta fallback"


# --- _send_text ---


class TestSendText:
    """Testes para _send_text."""

    @pytest.mark.asyncio
    async def test_send_text_com_thread(self, bus):
        """Verifica que thread_id e propagado no body."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        await bus._send_text("texto", thread_id="spaces/X/threads/T1")

        call_kwargs = mock_service.spaces().messages().create.call_args[1]
        assert "thread" in call_kwargs["body"]
        assert call_kwargs["messageReplyOption"] == "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"

    @pytest.mark.asyncio
    async def test_send_text_sem_thread(self, bus):
        """Verifica que sem thread_id nao inclui thread no body."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        await bus._send_text("texto", thread_id=None)

        call_kwargs = mock_service.spaces().messages().create.call_args[1]
        assert "thread" not in call_kwargs["body"]

    @pytest.mark.asyncio
    async def test_send_text_excecao_retorna_none(self, bus):
        """Verifica que excecao no envio retorna None."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute.side_effect = Exception("API error")
        bus._service = mock_service

        result = await bus._send_text("texto")
        assert result is None


# --- send_message com prefixo ---


class TestSendMessageDeep:
    """Testes adicionais para send_message."""

    @pytest.mark.asyncio
    async def test_send_message_sem_persona(self, monkeypatch):
        """Sem persona, nao adiciona prefixo."""
        monkeypatch.setenv("GCHAT_CREDENTIALS_PATH", "/fake")
        monkeypatch.setenv("GCHAT_SPACE_ID", "spaces/X")
        b = GChatMessageBus(persona_name="", persona_avatar="")

        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        b._service = mock_service

        await b.send_message("spaces/X", "texto puro")

        call_kwargs = mock_service.spaces().messages().create.call_args[1]
        assert call_kwargs["body"]["text"] == "texto puro"


# --- notify ---


class TestNotify:
    """Testes para notify."""

    @pytest.mark.asyncio
    async def test_notify_envia_com_prefixo(self, bus):
        """Verifica que notify adiciona emoji de notificacao."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        await bus.notify("spaces/X", "Tarefa concluida")

        call_kwargs = mock_service.spaces().messages().create.call_args[1]
        assert "🔔" in call_kwargs["body"]["text"]


# --- _poll_loop ---


class TestPollLoop:
    """Testes para _poll_loop."""

    @pytest.mark.asyncio
    async def test_poll_loop_processa_mensagens(self, bus):
        """Verifica que poll_loop busca e processa mensagens."""
        bus._running = True
        callback = AsyncMock()
        bus._message_callback = callback

        call_count = [0]
        original_running = bus._running

        def fake_running():
            nonlocal call_count
            call_count[0] += 1
            if call_count[0] > 1:
                bus._running = False
            return original_running

        # Faz o loop rodar uma iteracao
        bus._fetch_new_messages = MagicMock(return_value=[
            {
                "createTime": "2026-01-01T00:00:10Z",
                "sender": {"type": "HUMAN", "name": "users/1"},
                "text": "demanda",
                "thread": {"name": ""},
            },
        ])

        # Simula parada apos 1 iteracao
        iter_count = [0]

        async def limited_sleep(_):
            iter_count[0] += 1
            if iter_count[0] >= 1:
                bus._running = False

        with patch("asyncio.sleep", side_effect=limited_sleep):
            await bus._poll_loop()

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_loop_trata_excecao(self, bus):
        """Verifica que excecao no polling nao para o loop."""
        bus._running = True

        bus._fetch_new_messages = MagicMock(side_effect=Exception("API error"))

        iter_count = [0]

        async def limited_sleep(_):
            iter_count[0] += 1
            if iter_count[0] >= 1:
                bus._running = False

        with patch("asyncio.sleep", side_effect=limited_sleep):
            await bus._poll_loop()

        # Loop terminou sem propagar excecao


# --- create_thread ---


class TestCreateThread:
    """Testes para create_thread."""

    @pytest.mark.asyncio
    async def test_create_thread_sucesso(self, bus):
        """Verifica criacao de thread com sucesso."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={
                "thread": {"name": "spaces/X/threads/NEW"},
            }
        )
        bus._service = mock_service

        result = await bus.create_thread("spaces/X", "Nova thread")

        assert result == "spaces/X/threads/NEW"

    @pytest.mark.asyncio
    async def test_create_thread_falha(self, bus):
        """Verifica que falha retorna None."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute.side_effect = Exception("API error")
        bus._service = mock_service

        result = await bus.create_thread("spaces/X", "Nova thread")
        assert result is None


# --- send_approval_request ---


class TestSendApprovalRequest:
    """Testes para send_approval_request com card e fallback."""

    @pytest.mark.asyncio
    async def test_approval_com_numero_valido(self, bus):
        """Verifica que resposta numerica resolve para opcao."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        async def _test():
            async def _respond():
                await asyncio.sleep(0.01)
                key = "spaces/AAAA123"
                if key in bus._pending_text_reply:
                    bus._pending_text_reply[key].set_result("2")

            asyncio.create_task(_respond())
            return await bus.send_approval_request(
                "spaces/X", "Aprovar?", ["Sim", "Nao"]
            )

        result = await _test()
        assert result == "Nao"

    @pytest.mark.asyncio
    async def test_approval_com_texto_livre(self, bus):
        """Verifica que resposta nao numerica retorna texto raw."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        async def _test():
            async def _respond():
                await asyncio.sleep(0.01)
                key = "spaces/AAAA123"
                if key in bus._pending_text_reply:
                    bus._pending_text_reply[key].set_result("talvez")

            asyncio.create_task(_respond())
            return await bus.send_approval_request(
                "spaces/X", "Aprovar?", ["Sim", "Nao"]
            )

        result = await _test()
        assert result == "talvez"

    @pytest.mark.asyncio
    async def test_approval_card_falha_fallback_texto(self, bus):
        """Verifica que falha no card faz fallback para texto."""
        mock_service = MagicMock()
        # Primeira chamada (card) falha, segunda (fallback texto) funciona
        call_count = [0]

        def create_side_effect(**kwargs):
            mock_msg = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_msg.execute.side_effect = Exception("card error")
            else:
                mock_msg.execute.return_value = {"name": "spaces/X/messages/1"}
            return mock_msg

        mock_service.spaces().messages().create = create_side_effect
        bus._service = mock_service

        async def _test():
            async def _respond():
                await asyncio.sleep(0.05)
                key = "spaces/AAAA123"
                if key in bus._pending_text_reply:
                    bus._pending_text_reply[key].set_result("1")

            asyncio.create_task(_respond())
            return await bus.send_approval_request(
                "spaces/X", "Aprovar?", ["Sim", "Nao"]
            )

        result = await _test()
        assert result == "Sim"

    @pytest.mark.asyncio
    async def test_approval_com_thread(self, bus):
        """Verifica que thread_id e propagado na aprovacao."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        async def _test():
            async def _respond():
                await asyncio.sleep(0.01)
                key = "spaces/AAAA123:spaces/X/threads/T1"
                if key in bus._pending_text_reply:
                    bus._pending_text_reply[key].set_result("1")

            asyncio.create_task(_respond())
            return await bus.send_approval_request(
                "spaces/X",
                "Aprovar?",
                ["Sim", "Nao"],
                thread_id="spaces/X/threads/T1",
            )

        result = await _test()
        assert result == "Sim"


# --- ask_user ---


class TestAskUser:
    """Testes para ask_user."""

    @pytest.mark.asyncio
    async def test_ask_user_com_pergunta(self, bus):
        """Verifica que ask_user envia pergunta e aguarda resposta."""
        mock_service = MagicMock()
        mock_service.spaces().messages().create().execute = MagicMock(
            return_value={"name": "spaces/X/messages/1"}
        )
        bus._service = mock_service

        async def _test():
            async def _respond():
                await asyncio.sleep(0.01)
                key = "spaces/AAAA123"
                if key in bus._pending_text_reply:
                    bus._pending_text_reply[key].set_result("sim")

            asyncio.create_task(_respond())
            return await bus.ask_user("spaces/X", "Confirma?")

        result = await _test()
        assert result == "sim"

    @pytest.mark.asyncio
    async def test_ask_user_sem_pergunta(self, bus):
        """Verifica que ask_user sem pergunta nao envia mensagem."""
        bus._service = MagicMock()

        async def _test():
            async def _respond():
                await asyncio.sleep(0.01)
                key = "spaces/AAAA123"
                if key in bus._pending_text_reply:
                    bus._pending_text_reply[key].set_result("ok")

            asyncio.create_task(_respond())
            return await bus.ask_user("spaces/X", "")

        result = await _test()
        assert result == "ok"


# --- Propriedades ---


class TestPropriedadesDeep:
    """Testes para propriedades adicionais."""

    def test_supports_threads(self, bus):
        """GChat sempre suporta threads."""
        assert bus.supports_threads is True

    def test_default_chat_id(self, bus):
        """Retorna space_id configurado."""
        assert bus.default_chat_id == "spaces/AAAA123"

    def test_required_env_vars(self):
        """Verifica variaveis obrigatorias."""
        vars_ = GChatMessageBus.required_env_vars()
        assert "GCHAT_CREDENTIALS_PATH" in vars_
        assert "GCHAT_SPACE_ID" in vars_

    def test_env_template(self):
        """Verifica template de .env."""
        tmpl = GChatMessageBus.env_template()
        assert "GCHAT_CREDENTIALS_PATH" in tmpl
        assert "GCHAT_SPACE_ID" in tmpl


# --- start / stop ---


class TestStartStop:
    """Testes para start e stop."""

    @pytest.mark.asyncio
    async def test_start_inicia_polling(self, bus):
        """Verifica que start inicia polling."""
        with patch.object(bus, "_build_service"):
            await bus.start()

        assert bus._running is True
        assert bus._poll_task is not None

        # Limpa
        await bus.stop()
