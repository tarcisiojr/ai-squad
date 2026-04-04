"""Testes adicionais para cobertura profunda do claude_agent_sdk.py."""

from unittest.mock import MagicMock, patch

import pytest

from ai_squad.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter


class TestCompressPrompt:
    """Testes para _compress_prompt (linhas 378-408)."""

    def test_prompt_curto(self):
        """Prompt curto (<=50 linhas) mantém início e fim."""
        lines = [f"Linha {i}" for i in range(30)]
        prompt = "\n".join(lines)

        result = ClaudeAgentSDKAdapter._compress_prompt(prompt)
        assert "comprimido" in result
        # Deve ter removido linhas do meio
        assert len(result.split("\n")) < len(lines)

    def test_prompt_longo(self):
        """Prompt longo (>50 linhas) remove metade intermediária."""
        lines = [f"Linha {i}" for i in range(200)]
        prompt = "\n".join(lines)

        result = ClaudeAgentSDKAdapter._compress_prompt(prompt)
        assert "removidas" in result
        # Deve ser significativamente menor
        assert len(result.split("\n")) < len(lines)

    def test_prompt_muito_curto(self):
        """Prompt com poucas linhas ainda funciona."""
        prompt = "Linha 1\nLinha 2\nLinha 3"
        result = ClaudeAgentSDKAdapter._compress_prompt(prompt)
        assert isinstance(result, str)
        assert len(result) > 0


class TestBuildAddDirs:
    """Testes para _build_add_dirs (linhas 410-432)."""

    def test_com_agente_e_globais(self, tmp_path):
        """Retorna diretórios do agente e globais quando ambos existem."""
        agents_dir = tmp_path / "agents"
        (agents_dir / "dev").mkdir(parents=True)
        global_dir = tmp_path / "global-skills"
        global_dir.mkdir()

        adapter = ClaudeAgentSDKAdapter(
            agents_dir=str(agents_dir),
            global_skills_dir=str(global_dir),
        )

        dirs = adapter._build_add_dirs("dev")
        assert len(dirs) == 2
        assert str(agents_dir / "dev") in dirs
        assert str(global_dir) in dirs

    def test_sem_agent_name(self, tmp_path):
        """Sem agent_name, não inclui diretório do agente."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        global_dir = tmp_path / "global-skills"
        global_dir.mkdir()

        adapter = ClaudeAgentSDKAdapter(
            agents_dir=str(agents_dir),
            global_skills_dir=str(global_dir),
        )

        dirs = adapter._build_add_dirs("")
        # Apenas globais
        assert len(dirs) == 1

    def test_global_inexistente(self, tmp_path):
        """Diretório global inexistente não é incluído."""
        agents_dir = tmp_path / "agents"
        (agents_dir / "dev").mkdir(parents=True)

        adapter = ClaudeAgentSDKAdapter(
            agents_dir=str(agents_dir),
            global_skills_dir=str(tmp_path / "nao-existe"),
        )

        dirs = adapter._build_add_dirs("dev")
        assert len(dirs) == 1  # Apenas do agente


class TestSessionManagement:
    """Testes para gerenciamento de sessões."""

    def test_get_session_id_existente(self):
        """Retorna session_id quando existe."""
        adapter = ClaudeAgentSDKAdapter()
        adapter._sessions["d1"] = "session-abc"

        assert adapter.get_session_id("d1") == "session-abc"

    def test_get_session_id_inexistente(self):
        """Retorna None quando não existe."""
        adapter = ClaudeAgentSDKAdapter()
        assert adapter.get_session_id("d-inexistente") is None

    def test_clear_session(self):
        """Remove sessão existente."""
        adapter = ClaudeAgentSDKAdapter()
        adapter._sessions["d1"] = "session-abc"

        adapter.clear_session("d1")
        assert "d1" not in adapter._sessions

    def test_clear_session_inexistente(self):
        """Clear de sessão inexistente não falha."""
        adapter = ClaudeAgentSDKAdapter()
        adapter.clear_session("d-inexistente")  # Não deve lançar exceção


class TestBuildOptionsResume:
    """Testes para _build_options com resume de sessão."""

    def test_resume_sessao_existente(self):
        """Sessão existente gera resume nas opções."""
        adapter = ClaudeAgentSDKAdapter()
        adapter._sessions["d1"] = "session-abc-123"

        with patch("ai_squad.adapters.claude_agent_sdk.ClaudeAgentOptions") as mock_opts:
            adapter._build_options(conversation_id="d1")
            kwargs = mock_opts.call_args[1]
            assert kwargs["resume"] == "session-abc-123"

    def test_sem_resume_para_nova_conversa(self):
        """Nova conversa não tem resume."""
        adapter = ClaudeAgentSDKAdapter()

        with patch("ai_squad.adapters.claude_agent_sdk.ClaudeAgentOptions") as mock_opts:
            adapter._build_options(conversation_id="d-nova")
            kwargs = mock_opts.call_args[1]
            assert "resume" not in kwargs

    def test_options_com_agent_definitions(self):
        """Agent definitions são passadas nas opções."""
        adapter = ClaudeAgentSDKAdapter()
        mock_defs = {"po": MagicMock(), "dev": MagicMock()}
        adapter.set_agent_definitions(mock_defs)

        with patch("ai_squad.adapters.claude_agent_sdk.ClaudeAgentOptions") as mock_opts:
            adapter._build_options()
            kwargs = mock_opts.call_args[1]
            assert kwargs["agents"] == mock_defs


class TestRunWithModelOverride:
    """Testes para run com model_override."""

    @pytest.mark.asyncio
    async def test_model_override_restaura_original(self):
        """Model override restaura modelo original após execução."""
        adapter = ClaudeAgentSDKAdapter(model="claude-sonnet")

        mock_text_block = MagicMock()
        mock_text_block.text = "ok"
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        async def mock_query(**kwargs):
            yield mock_message

        with (
            patch("ai_squad.adapters.claude_agent_sdk.query", side_effect=mock_query),
            patch(
                "ai_squad.adapters.claude_agent_sdk.AssistantMessage",
                type(mock_message),
            ),
            patch(
                "ai_squad.adapters.claude_agent_sdk.TextBlock",
                type(mock_text_block),
            ),
        ):
            await adapter.run("test", {"model_override": "claude-opus"})

        # Modelo deve ter sido restaurado
        assert adapter._model == "claude-sonnet"

    @pytest.mark.asyncio
    async def test_model_override_restaura_apos_erro(self):
        """Model override restaura modelo mesmo após erro."""
        adapter = ClaudeAgentSDKAdapter(model="claude-sonnet", timeout=1)

        async def mock_query_erro(**kwargs):
            raise RuntimeError("Erro fatal")
            yield  # pragma: no cover

        with patch("ai_squad.adapters.claude_agent_sdk.query", side_effect=mock_query_erro):
            with pytest.raises(RuntimeError):
                await adapter.run("test", {"model_override": "claude-opus"})

        assert adapter._model == "claude-sonnet"


class TestRunWithImage:
    """Testes para run com image_path no contexto."""

    @pytest.mark.asyncio
    async def test_imagem_no_prompt(self):
        """Image_path no contexto adiciona instrução ao prompt."""
        adapter = ClaudeAgentSDKAdapter()

        mock_text_block = MagicMock()
        mock_text_block.text = "Analisei a imagem"
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        prompts_recebidos = []

        async def mock_query(**kwargs):
            prompts_recebidos.append(kwargs.get("prompt", ""))
            yield mock_message

        with (
            patch("ai_squad.adapters.claude_agent_sdk.query", side_effect=mock_query),
            patch(
                "ai_squad.adapters.claude_agent_sdk.AssistantMessage",
                type(mock_message),
            ),
            patch(
                "ai_squad.adapters.claude_agent_sdk.TextBlock",
                type(mock_text_block),
            ),
        ):
            result = await adapter.run("Analise", {"image_path": "/tmp/img.png"})

        assert result == "Analisei a imagem"


class TestSetAgentDefinitions:
    """Testes para set_agent_definitions."""

    def test_define_subagentes(self):
        """Define subagentes corretamente."""
        adapter = ClaudeAgentSDKAdapter()
        defs = {"po": MagicMock(), "dev": MagicMock()}

        adapter.set_agent_definitions(defs)
        assert adapter._agent_definitions == defs

    def test_none_por_padrao(self):
        """Agent definitions é None por padrão."""
        adapter = ClaudeAgentSDKAdapter()
        assert adapter._agent_definitions is None


class TestExecuteSdkContextLengthExceeded:
    """Testes para _execute_sdk com context_length_exceeded."""

    @pytest.mark.asyncio
    async def test_compress_e_retry_context_length(self):
        """Context length exceeded comprime prompt e retenta."""
        adapter = ClaudeAgentSDKAdapter(timeout=5)

        call_count = [0]
        mock_text_block = MagicMock()
        mock_text_block.text = "ok"
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        async def mock_query(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("context_length_exceeded: prompt too long")
            yield mock_message

        with (
            patch("ai_squad.adapters.claude_agent_sdk.query", side_effect=mock_query),
            patch(
                "ai_squad.adapters.claude_agent_sdk.AssistantMessage",
                type(mock_message),
            ),
            patch(
                "ai_squad.adapters.claude_agent_sdk.TextBlock",
                type(mock_text_block),
            ),
        ):
            prompt = "\n".join(f"Linha {i}" for i in range(100))
            result = await adapter._execute_sdk(prompt, "d1", 5, "dev", 5)
            assert result == "ok"
            assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_limpa_sessao_no_context_length(self):
        """Context length exceeded limpa sessão para forçar nova conversa."""
        adapter = ClaudeAgentSDKAdapter(timeout=5)
        adapter._sessions["d1"] = "session-old"

        call_count = [0]
        mock_text_block = MagicMock()
        mock_text_block.text = "ok"
        mock_message = MagicMock()
        mock_message.content = [mock_text_block]

        async def mock_query(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("prompt too long for context")
            yield mock_message

        with (
            patch("ai_squad.adapters.claude_agent_sdk.query", side_effect=mock_query),
            patch(
                "ai_squad.adapters.claude_agent_sdk.AssistantMessage",
                type(mock_message),
            ),
            patch(
                "ai_squad.adapters.claude_agent_sdk.TextBlock",
                type(mock_text_block),
            ),
        ):
            await adapter._execute_sdk("prompt", "d1", 5, "dev", 5)
            # Sessão deve ter sido limpa
            assert "d1" not in adapter._sessions


class TestBuildOptionsStderr:
    """Testes para stderr redirect em _build_options."""

    def test_stderr_to_log_gera_callback(self):
        """stderr_to_log=True gera callback de stderr."""
        adapter = ClaudeAgentSDKAdapter()
        adapter._stderr_to_log = True

        with patch("ai_squad.adapters.claude_agent_sdk.ClaudeAgentOptions") as mock_opts:
            adapter._build_options()
            kwargs = mock_opts.call_args[1]
            assert "stderr" in kwargs
            assert callable(kwargs["stderr"])

    def test_sem_stderr_redirect(self):
        """stderr_to_log=False não gera callback."""
        adapter = ClaudeAgentSDKAdapter()
        adapter._stderr_to_log = False

        with patch("ai_squad.adapters.claude_agent_sdk.ClaudeAgentOptions") as mock_opts:
            adapter._build_options()
            kwargs = mock_opts.call_args[1]
            assert "stderr" not in kwargs
