"""Testes adicionais para cobertura do daemon — caminhos não cobertos."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from ai_squad.daemon import Daemon
from ai_squad.orchestrator.tools import RunningAgent


def _mock_bus(chat_id: str = "12345") -> MagicMock:
    """Cria mock de MessageBus com default_chat_id configurado."""
    bus = AsyncMock()
    type(bus).default_chat_id = PropertyMock(return_value=chat_id)
    type(bus).supports_threads = PropertyMock(return_value=False)
    type(bus).bot_identifier = PropertyMock(return_value="squadbot")
    return bus


def _daemon_with_mocks(
    agents: dict | None = None,
    chat_id: str = "12345",
) -> Daemon:
    """Cria Daemon com bus, engine e config mockados."""
    daemon = Daemon()
    daemon._bus = _mock_bus(chat_id)
    daemon._engine = AsyncMock()
    daemon._config = MagicMock()
    daemon._config.agents = agents or {}
    daemon._config.activation_mode = "mention"
    daemon._thread_map = None
    daemon._thread_tracker = None
    return daemon


class TestSlugifyEdgeCases:
    """Testes adicionais para _slugify."""

    def test_slugify_apenas_caracteres_especiais(self):
        """Texto sem caracteres alfanuméricos retorna 'demanda'."""
        assert Daemon._slugify("!@#$%^&*()") == "demanda"

    def test_slugify_com_acentos_complexos(self):
        """Acentos complexos são removidos corretamente."""
        result = Daemon._slugify("Módulo de integração")
        assert "modulo" in result
        assert "integracao" in result

    def test_slugify_max_words_customizado(self):
        """Verifica limite de palavras customizado."""
        result = Daemon._slugify("uma dois tres quatro cinco seis", max_words=3)
        assert result == "uma-dois-tres"

    def test_slugify_texto_com_numeros(self):
        """Texto com números preserva os números."""
        result = Daemon._slugify("Bug 123 na API v2")
        assert "123" in result
        assert "v2" in result

    def test_slugify_unicode_cjk(self):
        """Caracteres CJK são removidos (ASCII only)."""
        result = Daemon._slugify("テスト test")
        assert result == "test"

    def test_slugify_espacos_multiplos(self):
        """Múltiplos espaços não geram hífens duplicados."""
        result = Daemon._slugify("hello    world")
        assert "--" not in result
        assert result == "hello-world"


class TestGenerateDemandId:
    """Testes adicionais para geração de demand_id."""

    def test_demand_id_formato(self):
        """demand_id tem formato slug-4hex."""
        daemon = Daemon()
        did = daemon._generate_demand_id("Teste simples")
        parts = did.rsplit("-", 1)
        assert len(parts) == 2
        assert len(parts[1]) == 4
        # Verifica que é hex válido
        int(parts[1], 16)

    def test_demand_id_unico(self):
        """Dois demand_ids para o mesmo texto são diferentes."""
        daemon = Daemon()
        id1 = daemon._generate_demand_id("Mesmo texto")
        id2 = daemon._generate_demand_id("Mesmo texto")
        assert id1 != id2


class TestBuildAgentCommands:
    """Testes para construção de mapeamento comando → agente."""

    def test_sem_agentes(self):
        """Config sem agentes retorna dicionário vazio."""
        daemon = Daemon()
        daemon._config = MagicMock()
        daemon._config.agents = {}
        assert daemon._build_agent_commands() == {}

    def test_com_comandos_customizados(self):
        """Agentes com comando customizado são mapeados corretamente."""
        daemon = Daemon()
        daemon._config = MagicMock()
        agent_po = MagicMock()
        agent_po.command = "/po"
        agent_dev = MagicMock()
        agent_dev.command = "/dev-back"
        daemon._config.agents = {"po": agent_po, "dev-backend": agent_dev}

        cmds = daemon._build_agent_commands()
        assert cmds["/po"] == "po"
        assert cmds["/dev-back"] == "dev-backend"

    def test_comando_padrao_quando_vazio(self):
        """Agente sem comando customizado usa /<agent_id>."""
        daemon = Daemon()
        daemon._config = MagicMock()
        agent = MagicMock()
        agent.command = ""
        daemon._config.agents = {"qa": agent}

        cmds = daemon._build_agent_commands()
        assert cmds["/qa"] == "qa"

    def test_config_none_retorna_vazio(self):
        """Config None retorna dicionário vazio."""
        daemon = Daemon()
        daemon._config = None
        assert daemon._build_agent_commands() == {}


class TestHandleNewDemandCommands:
    """Testes para comandos especiais em _handle_new_demand."""

    @pytest.mark.asyncio
    async def test_comando_help_case_insensitive(self):
        """Comando /HELP funciona case insensitive."""
        daemon = _daemon_with_mocks()
        daemon._config.squad_lead = MagicMock()
        daemon._config.squad_lead.name = "Squad Lead"

        await daemon._handle_new_demand("/HELP")
        daemon._bus.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_comando_status(self):
        """/status retorna status dos agentes."""
        daemon = _daemon_with_mocks()
        daemon._engine.get_running_agents_status.return_value = "Nenhum agente ativo."

        await daemon._handle_new_demand("/status")
        daemon._bus.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_comando_stop(self):
        """/stop para agentes."""
        daemon = _daemon_with_mocks()
        daemon._engine = MagicMock()
        daemon._engine.get_running_agents.return_value = {}

        await daemon._handle_new_demand("/stop")
        daemon._bus.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_comando_skills(self):
        """/skills lista skills."""
        daemon = _daemon_with_mocks()

        await daemon._handle_new_demand("/skills")
        daemon._bus.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_comando_agente_sem_texto(self):
        """Comando de agente sem texto mostra instruções de uso."""
        from ai_squad.factory import AgentConfig

        agent = MagicMock()
        agent.command = "/po"
        agent.name = "PO Agent"
        daemon = _daemon_with_mocks(agents={"po": agent})

        await daemon._handle_new_demand("/po")
        daemon._bus.send_message.assert_called_once()
        msg = daemon._bus.send_message.call_args[0][1]
        assert "Use:" in msg

    @pytest.mark.asyncio
    async def test_comando_agente_com_texto(self):
        """Comando de agente com texto inicia conversa direta."""
        agent = MagicMock()
        agent.command = "/po"
        agent.name = "PO Agent"
        daemon = _daemon_with_mocks(agents={"po": agent})

        await daemon._handle_new_demand("/po Analisar requisitos")

        # Espera um pouco para a task ser criada
        import asyncio
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_imagem_temporaria_removida_apos_processamento(self, tmp_path):
        """Imagem temporária é removida após processamento."""
        img = tmp_path / "temp.png"
        img.write_bytes(b"\x89PNG")

        daemon = _daemon_with_mocks()

        await daemon._handle_new_demand("Texto", str(img))

        assert not img.exists()

    @pytest.mark.asyncio
    async def test_erro_notifica_e_continua(self):
        """Erro no engine notifica usuário e não propaga exceção."""
        daemon = _daemon_with_mocks()
        daemon._engine.run_squad_lead.side_effect = RuntimeError("Boom")

        # Não deve lançar exceção
        await daemon._handle_new_demand("Texto que falha")
        daemon._bus.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_chat_id_para_user_id(self):
        """Se default_chat_id é vazio, usa user_id."""
        daemon = _daemon_with_mocks(chat_id="")

        await daemon._handle_new_demand("Texto", user_id="user42")

        daemon._engine.run_squad_lead.assert_called_once()
        call_args = daemon._engine.run_squad_lead.call_args
        assert call_args[0][1] == "user42"


class TestSendStatus:
    """Testes para _send_status."""

    @pytest.mark.asyncio
    async def test_status_sem_thread(self):
        """Status sem thread retorna status geral."""
        daemon = _daemon_with_mocks()
        daemon._engine = MagicMock()
        daemon._engine.get_running_agents_status.return_value = "Status geral"

        await daemon._send_status("12345")
        daemon._bus.send_message.assert_called_once_with("12345", "Status geral", thread_id=None)

    @pytest.mark.asyncio
    async def test_status_com_thread_mapeada(self):
        """Status em thread mapeada filtra por demanda."""
        daemon = _daemon_with_mocks()
        daemon._engine = MagicMock()
        daemon._thread_map = MagicMock()
        daemon._thread_map.get_demand.return_value = "demanda-1234"

        # Mock do engine status
        engine_status = MagicMock()
        engine_status.squad_lead_busy = False
        engine_status.running_agents = {}
        daemon._engine.get_status.return_value = engine_status

        await daemon._send_status("12345", thread_id="thread-1")

        daemon._bus.send_message.assert_called_once()
        msg = daemon._bus.send_message.call_args[0][1]
        assert "demanda-1234" in msg

    @pytest.mark.asyncio
    async def test_status_com_thread_squad_lead_busy(self):
        """Status mostra Squad Lead processando quando busy na mesma demanda."""
        daemon = _daemon_with_mocks()
        daemon._engine = MagicMock()
        daemon._thread_map = MagicMock()
        daemon._thread_map.get_demand.return_value = "demanda-abc"

        import time

        engine_status = MagicMock()
        engine_status.squad_lead_busy = True
        engine_status.current_demand_id = "demanda-abc"
        engine_status.squad_lead_since = time.time() - 10
        engine_status.running_agents = {}
        engine_status.personas = {}
        daemon._engine.get_status.return_value = engine_status
        daemon._engine.get_agent_label.return_value = "Squad Lead"

        await daemon._send_status("12345", thread_id="thread-1")

        msg = daemon._bus.send_message.call_args[0][1]
        assert "Squad Lead" in msg


class TestStopAgents:
    """Testes adicionais para _stop_agents."""

    @pytest.mark.asyncio
    async def test_stop_agente_especifico_inexistente(self):
        """Parar agente inexistente retorna mensagem de erro."""
        daemon = _daemon_with_mocks()
        daemon._engine = MagicMock()
        running = {
            "dev": RunningAgent(
                agent_name="dev", demand_id="d1", user_id="u1", status="running", task=MagicMock()
            )
        }
        daemon._engine.get_running_agents.return_value = running
        daemon._engine.stop_agent.return_value = True
        daemon._engine.get_agent_label.side_effect = lambda n: n

        await daemon._stop_agents("12345", "/stop qa")

        msg = daemon._bus.send_message.call_args[0][1]
        assert "nao encontrado" in msg

    @pytest.mark.asyncio
    async def test_stop_agente_nao_rodando(self):
        """Agente que não está running não é parado."""
        daemon = _daemon_with_mocks()
        daemon._engine = MagicMock()
        running = {
            "dev": RunningAgent(
                agent_name="dev", demand_id="d1", user_id="u1", status="completed", task=None
            )
        }
        daemon._engine.get_running_agents.return_value = running

        await daemon._stop_agents("12345", "/stop")

        msg = daemon._bus.send_message.call_args[0][1]
        assert "Nenhum agente em execucao" in msg


class TestSendHelp:
    """Testes para _send_help."""

    @pytest.mark.asyncio
    async def test_help_com_agentes(self):
        """Help lista comandos de agentes configurados."""
        daemon = _daemon_with_mocks()
        agent = MagicMock()
        agent.command = "/po"
        agent.name = "PO Agent"
        daemon._config.agents = {"po": agent}
        daemon._config.squad_lead = MagicMock()
        daemon._config.squad_lead.name = "Squad Lead"

        await daemon._send_help("12345")

        msg = daemon._bus.send_message.call_args[0][1]
        assert "/po" in msg
        assert "PO Agent" in msg
        assert "/status" in msg
        assert "/help" in msg

    @pytest.mark.asyncio
    async def test_help_sem_config(self):
        """Help funciona mesmo com config parcial."""
        daemon = _daemon_with_mocks()
        daemon._config = None

        await daemon._send_help("12345")

        daemon._bus.send_message.assert_called_once()


class TestSendSkills:
    """Testes para _send_skills."""

    @pytest.mark.asyncio
    async def test_skills_com_diretorio_global(self, tmp_path):
        """Lista skills globais quando existem."""
        from ai_squad.path_resolver import PathResolver

        daemon = Daemon()
        daemon._bus = _mock_bus()
        daemon._paths = MagicMock()
        daemon._paths.global_skills_dir = tmp_path / "global_skills"
        daemon._paths.agents_dir = tmp_path / "agents"
        daemon._paths.workspace = tmp_path / "workspace"

        # Cria skill global
        skill_dir = daemon._paths.global_skills_dir / "minha-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Skill")

        # Cria diretórios necessários
        daemon._paths.agents_dir.mkdir(parents=True)
        (daemon._paths.workspace / ".claude" / "skills").mkdir(parents=True, exist_ok=True)

        await daemon._send_skills("12345")

        msg = daemon._bus.send_message.call_args[0][1]
        assert "minha-skill" in msg

    @pytest.mark.asyncio
    async def test_skills_sem_nenhuma(self, tmp_path):
        """Mostra mensagem quando não há skills."""
        daemon = Daemon()
        daemon._bus = _mock_bus()
        daemon._paths = MagicMock()
        daemon._paths.global_skills_dir = tmp_path / "vazio"
        daemon._paths.agents_dir = tmp_path / "agents_vazio"
        daemon._paths.workspace = tmp_path / "ws_vazio"

        await daemon._send_skills("12345")

        msg = daemon._bus.send_message.call_args[0][1]
        assert "Nenhuma" in msg or "nenhuma" in msg

    @pytest.mark.asyncio
    async def test_skills_por_agente(self, tmp_path):
        """Lista skills por agente quando existem."""
        daemon = Daemon()
        daemon._bus = _mock_bus()
        daemon._paths = MagicMock()
        daemon._paths.global_skills_dir = tmp_path / "global"
        daemon._paths.agents_dir = tmp_path / "agents"
        daemon._paths.workspace = tmp_path / "ws"

        # Cria skill por agente
        agent_skill = tmp_path / "agents" / "dev" / "skills" / "code-review"
        agent_skill.mkdir(parents=True)
        (agent_skill / "SKILL.md").write_text("# Code Review")

        await daemon._send_skills("12345")

        msg = daemon._bus.send_message.call_args[0][1]
        assert "code-review" in msg

    @pytest.mark.asyncio
    async def test_skills_do_projeto(self, tmp_path):
        """Lista skills do projeto quando existem."""
        daemon = Daemon()
        daemon._bus = _mock_bus()
        daemon._paths = MagicMock()
        daemon._paths.global_skills_dir = tmp_path / "global"
        daemon._paths.agents_dir = tmp_path / "agents"
        daemon._paths.workspace = tmp_path / "ws"

        # Cria skill do projeto
        proj_skill = tmp_path / "ws" / ".claude" / "skills" / "deploy"
        proj_skill.mkdir(parents=True)
        (proj_skill / "SKILL.md").write_text("# Deploy")

        await daemon._send_skills("12345")

        msg = daemon._bus.send_message.call_args[0][1]
        assert "deploy" in msg


class TestHeartbeatLoop:
    """Testes para o loop de heartbeat."""

    @pytest.mark.asyncio
    async def test_heartbeat_desabilitado(self):
        """Heartbeat desabilitado retorna imediatamente."""
        daemon = Daemon()
        daemon._config = MagicMock()
        daemon._config.heartbeat.enabled = False

        # Não deve travar
        await daemon._heartbeat_loop()

    @pytest.mark.asyncio
    async def test_heartbeat_sem_config(self):
        """Heartbeat sem config retorna imediatamente."""
        daemon = Daemon()
        daemon._config = None

        await daemon._heartbeat_loop()


class TestHeartbeatLoopWithStalled:
    """Testes para heartbeat com demandas paradas."""

    @pytest.mark.asyncio
    async def test_heartbeat_retoma_demanda_parada(self):
        """Heartbeat retoma demandas paradas automaticamente."""
        daemon = _daemon_with_mocks()
        daemon._config = MagicMock()
        daemon._config.heartbeat.enabled = True
        daemon._config.heartbeat.interval = 1
        daemon._config.heartbeat.stall_timeout = 60
        daemon._config.heartbeat.reminder_timeout = 300
        daemon._config.heartbeat.max_auto_retries = 3
        daemon._config.state_dir = "/tmp/test-state"

        engine = MagicMock()
        engine.run_squad_lead = AsyncMock()
        daemon._engine = engine

        # Mock do JournalStore
        with patch("ai_squad.daemon.JournalStore") as MockJournal:
            journal = MockJournal.return_value
            journal.get_stalled.return_value = [
                {
                    "demand_id": "d1",
                    "demand_text": "Criar API",
                    "auto_retries": 0,
                    "current_phase": "dev",
                    "next_expected": {"description": "Review"},
                }
            ]
            journal.get_pending_approvals.return_value = []

            # Faz o loop rodar uma iteração e parar
            call_count = [0]
            original_is_set = daemon._shutdown_event.is_set

            def is_set_once():
                call_count[0] += 1
                if call_count[0] <= 1:
                    return False  # Primeira check: não está setado
                return True  # Segunda check: para o loop

            daemon._shutdown_event.is_set = is_set_once

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await daemon._heartbeat_loop()

            engine.run_squad_lead.assert_called_once()
            assert "RETOMADA" in engine.run_squad_lead.call_args[0][2]

    @pytest.mark.asyncio
    async def test_heartbeat_max_retries(self):
        """Heartbeat não retoma se max_retries atingido."""
        daemon = _daemon_with_mocks()
        daemon._config = MagicMock()
        daemon._config.heartbeat.enabled = True
        daemon._config.heartbeat.interval = 1
        daemon._config.heartbeat.stall_timeout = 60
        daemon._config.heartbeat.reminder_timeout = 300
        daemon._config.heartbeat.max_auto_retries = 3
        daemon._config.state_dir = "/tmp/test-state"

        engine = MagicMock()
        engine.run_squad_lead = AsyncMock()
        daemon._engine = engine

        with patch("ai_squad.daemon.JournalStore") as MockJournal:
            journal = MockJournal.return_value
            journal.get_stalled.return_value = [
                {
                    "demand_id": "d1",
                    "demand_text": "X",
                    "auto_retries": 3,  # Atingiu max
                }
            ]
            journal.get_pending_approvals.return_value = []

            call_count = [0]

            def is_set_once():
                call_count[0] += 1
                return call_count[0] > 1

            daemon._shutdown_event.is_set = is_set_once

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await daemon._heartbeat_loop()

            engine.run_squad_lead.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_lembrete_aprovacao(self):
        """Heartbeat envia lembrete para aprovações pendentes."""
        daemon = _daemon_with_mocks()
        daemon._config = MagicMock()
        daemon._config.heartbeat.enabled = True
        daemon._config.heartbeat.interval = 1
        daemon._config.heartbeat.stall_timeout = 60
        daemon._config.heartbeat.reminder_timeout = 300
        daemon._config.heartbeat.max_auto_retries = 3
        daemon._config.state_dir = "/tmp/test-state"

        with patch("ai_squad.daemon.JournalStore") as MockJournal:
            journal = MockJournal.return_value
            journal.get_stalled.return_value = []
            journal.get_pending_approvals.return_value = [
                {"demand_text": "Feature X"}
            ]

            call_count = [0]

            def is_set_once():
                call_count[0] += 1
                return call_count[0] > 1

            daemon._shutdown_event.is_set = is_set_once

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await daemon._heartbeat_loop()

            daemon._bus.send_message.assert_called_once()
            msg = daemon._bus.send_message.call_args[0][1]
            assert "Lembrete" in msg
            assert "Feature X" in msg


class TestShutdown:
    """Testes para graceful shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_com_adapter(self):
        """Shutdown chama adapter.shutdown()."""
        daemon = Daemon()
        daemon._bus = _mock_bus()
        daemon._adapter = AsyncMock()

        await daemon._shutdown()

        daemon._adapter.shutdown.assert_called_once()
        assert daemon._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_sem_bus(self):
        """Shutdown funciona mesmo sem bus inicializado."""
        daemon = Daemon()

        await daemon._shutdown()

        assert daemon._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_adapter_com_erro(self):
        """Shutdown continua mesmo se adapter.shutdown() falha."""
        daemon = Daemon()
        daemon._bus = _mock_bus()
        daemon._adapter = AsyncMock()
        daemon._adapter.shutdown.side_effect = RuntimeError("Erro no shutdown")

        await daemon._shutdown()

        assert daemon._shutdown_event.is_set()


class TestLoadConfig:
    """Testes adicionais para _load_config."""

    def test_env_override_light_model(self, monkeypatch, tmp_path):
        """LIGHT_MODEL é sobrescrito por env var."""
        from ai_squad.path_resolver import PathResolver

        paths = PathResolver("local", tmp_path)
        (tmp_path / ".ai-squad").mkdir(exist_ok=True)

        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("MESSAGING_PROVIDER", raising=False)
        monkeypatch.setenv("LIGHT_MODEL", "gpt-4o-mini")

        daemon = Daemon(path_resolver=paths)
        config = daemon._load_config()

        assert config.light_model == "gpt-4o-mini"

    def test_env_override_heavy_model(self, monkeypatch, tmp_path):
        """HEAVY_MODEL é sobrescrito por env var."""
        from ai_squad.path_resolver import PathResolver

        paths = PathResolver("local", tmp_path)
        (tmp_path / ".ai-squad").mkdir(exist_ok=True)

        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("MESSAGING_PROVIDER", raising=False)
        monkeypatch.setenv("HEAVY_MODEL", "claude-opus")

        daemon = Daemon(path_resolver=paths)
        config = daemon._load_config()

        assert config.heavy_model == "claude-opus"

    def test_env_override_state_dir(self, monkeypatch, tmp_path):
        """STATE_DIR é sobrescrito por env var."""
        from ai_squad.path_resolver import PathResolver

        paths = PathResolver("local", tmp_path)
        (tmp_path / ".ai-squad").mkdir(exist_ok=True)

        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("MESSAGING_PROVIDER", raising=False)
        monkeypatch.setenv("STATE_DIR", "/custom/state")

        daemon = Daemon(path_resolver=paths)
        config = daemon._load_config()

        assert config.state_dir == "/custom/state"

    def test_env_override_repo_path(self, monkeypatch, tmp_path):
        """REPO_PATH é sobrescrito por env var."""
        from ai_squad.path_resolver import PathResolver

        paths = PathResolver("local", tmp_path)
        (tmp_path / ".ai-squad").mkdir(exist_ok=True)

        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("MESSAGING_PROVIDER", raising=False)
        monkeypatch.setenv("REPO_PATH", "/custom/repo")

        daemon = Daemon(path_resolver=paths)
        config = daemon._load_config()

        assert config.repo_path == "/custom/repo"


class TestCreateDemandTopic:
    """Testes para _create_demand_topic."""

    @pytest.mark.asyncio
    async def test_cria_topico_e_mapeia(self):
        """Cria tópico e persiste mapeamento."""
        daemon = Daemon()
        daemon._bus = _mock_bus()
        type(daemon._bus).supports_threads = PropertyMock(return_value=True)
        daemon._bus.create_thread.return_value = "thread-123"
        daemon._thread_map = MagicMock()

        result = await daemon._create_demand_topic("demand-1", "Título da demanda")

        assert result == "thread-123"
        daemon._thread_map.add.assert_called_once_with("thread-123", "demand-1")

    @pytest.mark.asyncio
    async def test_sem_suporte_threads(self):
        """Retorna None se bus não suporta threads."""
        daemon = Daemon()
        daemon._bus = _mock_bus()
        type(daemon._bus).supports_threads = PropertyMock(return_value=False)
        daemon._thread_map = MagicMock()

        result = await daemon._create_demand_topic("demand-1", "Título")
        assert result is None

    @pytest.mark.asyncio
    async def test_sem_thread_map(self):
        """Retorna None se thread_map não está configurado."""
        daemon = Daemon()
        daemon._bus = _mock_bus()
        type(daemon._bus).supports_threads = PropertyMock(return_value=True)
        daemon._thread_map = None

        result = await daemon._create_demand_topic("demand-1", "Título")
        assert result is None


class TestHandleNewDemandThreadRouting:
    """Testes para roteamento por thread em _handle_new_demand."""

    @pytest.mark.asyncio
    async def test_thread_mapeada_envia_para_demand(self):
        """Thread mapeada roteia para demand_id correto."""
        daemon = _daemon_with_mocks()
        daemon._thread_map = MagicMock()
        daemon._thread_map.get_demand.return_value = "demanda-existente"

        await daemon._handle_new_demand(
            "Mensagem no tópico", thread_id="thread-1"
        )

        daemon._engine.run_squad_lead.assert_called_once()
        call_args = daemon._engine.run_squad_lead.call_args
        assert call_args[0][0] == "demanda-existente"

    @pytest.mark.asyncio
    async def test_thread_nova_cria_mapeamento(self):
        """Thread nova sem mapeamento cria demand_id e mapeia."""
        daemon = _daemon_with_mocks()
        daemon._thread_map = MagicMock()
        daemon._thread_map.get_demand.return_value = None

        await daemon._handle_new_demand(
            "Nova mensagem no tópico", thread_id="thread-novo"
        )

        # Deve ter criado mapeamento
        daemon._thread_map.add.assert_called_once()
        # Deve ter chamado run_squad_lead com o novo demand_id
        daemon._engine.run_squad_lead.assert_called_once()


class TestResumePendingWork:
    """Testes para _resume_pending_work."""

    @pytest.mark.asyncio
    async def test_sem_chat_id(self):
        """Retorna sem fazer nada quando não há chat_id."""
        daemon = _daemon_with_mocks(chat_id="")
        engine = MagicMock()
        engine.run_squad_lead = AsyncMock()
        daemon._engine = engine

        await daemon._resume_pending_work()
        engine.run_squad_lead.assert_not_called()

    @pytest.mark.asyncio
    async def test_sem_trabalho_pendente(self):
        """Retorna sem fazer nada quando não há trabalho pendente."""
        daemon = _daemon_with_mocks()
        engine = MagicMock()
        journal = MagicMock()
        journal.get_active_summaries.return_value = "Nenhuma demanda ativa."
        engine.get_journal.return_value = journal
        daemon._engine = engine
        daemon._state_manager = MagicMock()
        daemon._state_manager.get_pending_demands.return_value = []

        await daemon._resume_pending_work()

    @pytest.mark.asyncio
    async def test_com_demanda_pendente(self):
        """Retoma quando há demandas pendentes no state manager."""
        daemon = _daemon_with_mocks()
        engine = MagicMock()
        journal = MagicMock()
        journal.get_active_summaries.return_value = "Nenhuma demanda ativa."
        engine.get_journal.return_value = journal
        engine.run_squad_lead = AsyncMock()
        daemon._engine = engine
        daemon._state_manager = MagicMock()
        daemon._state_manager.get_pending_demands.return_value = [
            {"demand_id": "d1", "state": "in_progress"}
        ]

        await daemon._resume_pending_work()

        engine.run_squad_lead.assert_called_once()
        call_args = engine.run_squad_lead.call_args[0]
        assert "squad-lead-session" in call_args[0]
        assert "REINICIOU" in call_args[2]

    @pytest.mark.asyncio
    async def test_com_journal_ativo(self):
        """Retoma quando journal tem decisões ativas."""
        daemon = _daemon_with_mocks()
        # Engine precisa ser MagicMock para métodos sync + AsyncMock para async
        engine = MagicMock()
        journal = MagicMock()
        journal.get_active_summaries.return_value = "Demanda d1: em andamento"
        engine.get_journal.return_value = journal
        engine.run_squad_lead = AsyncMock()
        daemon._engine = engine
        daemon._state_manager = MagicMock()
        daemon._state_manager.get_pending_demands.return_value = []

        await daemon._resume_pending_work()

        engine.run_squad_lead.assert_called_once()

    @pytest.mark.asyncio
    async def test_erro_no_journal(self):
        """Continua mesmo com erro ao ler journal."""
        daemon = _daemon_with_mocks()
        engine = MagicMock()
        engine.get_journal.side_effect = RuntimeError("Erro")
        engine.run_squad_lead = AsyncMock()
        daemon._engine = engine
        daemon._state_manager = MagicMock()
        daemon._state_manager.get_pending_demands.return_value = []

        # Não deve lançar exceção
        await daemon._resume_pending_work()

    @pytest.mark.asyncio
    async def test_erro_no_resume(self):
        """Erro na retomada é capturado."""
        daemon = _daemon_with_mocks()
        engine = MagicMock()
        journal = MagicMock()
        journal.get_active_summaries.return_value = "Ativo"
        engine.get_journal.return_value = journal
        engine.run_squad_lead = AsyncMock(side_effect=RuntimeError("Falha"))
        daemon._engine = engine
        daemon._state_manager = MagicMock()
        daemon._state_manager.get_pending_demands.return_value = []

        # Não deve lançar exceção
        await daemon._resume_pending_work()


class TestHandleNewDemandThreadTracker:
    """Testes para lógica de ThreadTracker em _handle_new_demand."""

    @pytest.mark.asyncio
    async def test_thread_tracker_ignore(self):
        """ThreadTracker IGNORE faz retornar sem processar."""
        from ai_squad.orchestrator.thread_tracker import ThreadAction

        daemon = _daemon_with_mocks()
        daemon._thread_tracker = MagicMock()
        daemon._thread_tracker.on_message.return_value = ThreadAction.IGNORE

        await daemon._handle_new_demand(
            "Mensagem ignorada", thread_id="thread-1"
        )

        # Não deve chamar engine
        daemon._engine.run_squad_lead.assert_not_called()

    @pytest.mark.asyncio
    async def test_thread_tracker_handoff(self):
        """ThreadTracker HANDOFF envia mensagem de handoff."""
        from ai_squad.orchestrator.thread_tracker import ThreadAction

        daemon = _daemon_with_mocks()
        daemon._thread_tracker = MagicMock()
        daemon._thread_tracker.on_message.return_value = ThreadAction.HANDOFF
        daemon._thread_tracker.handoff_message_enabled = True

        await daemon._handle_new_demand(
            "Mensagem handoff", thread_id="thread-1"
        )

        daemon._bus.send_message.assert_called_once()
        msg = daemon._bus.send_message.call_args[0][1]
        assert "assumiu" in msg

    @pytest.mark.asyncio
    async def test_thread_tracker_handoff_sem_mensagem(self):
        """ThreadTracker HANDOFF sem mensagem habilitada retorna silenciosamente."""
        from ai_squad.orchestrator.thread_tracker import ThreadAction

        daemon = _daemon_with_mocks()
        daemon._thread_tracker = MagicMock()
        daemon._thread_tracker.on_message.return_value = ThreadAction.HANDOFF
        daemon._thread_tracker.handoff_message_enabled = False

        await daemon._handle_new_demand(
            "Mensagem handoff", thread_id="thread-1"
        )

        daemon._bus.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_activation_all_pula_tracker(self):
        """activation_mode 'all' pula ThreadTracker."""
        from ai_squad.orchestrator.thread_tracker import ThreadAction

        daemon = _daemon_with_mocks()
        daemon._config.activation_mode = "all"
        daemon._thread_tracker = MagicMock()
        daemon._thread_map = MagicMock()
        daemon._thread_map.get_demand.return_value = "d1"

        await daemon._handle_new_demand(
            "Mensagem processada", thread_id="thread-1"
        )

        # ThreadTracker NÃO deve ter sido consultado
        daemon._thread_tracker.on_message.assert_not_called()
        # Mas engine deve processar
        daemon._engine.run_squad_lead.assert_called_once()


class TestStandbyTimeoutLoop:
    """Testes para _standby_timeout_loop."""

    @pytest.mark.asyncio
    async def test_sem_thread_tracker(self):
        """Loop retorna imediatamente sem thread_tracker."""
        daemon = Daemon()
        daemon._thread_tracker = None

        await daemon._standby_timeout_loop()


class TestRunDirectAgent:
    """Testes para _run_direct_agent."""

    @pytest.mark.asyncio
    async def test_conversa_direta_ok(self):
        """Conversa direta com agente funciona."""
        daemon = _daemon_with_mocks()

        await daemon._run_direct_agent("d1", "12345", "dev", "Criar API")

        daemon._engine.direct_agent_conversation.assert_called_once_with(
            "d1", "12345", "dev", "Criar API"
        )

    @pytest.mark.asyncio
    async def test_conversa_direta_erro(self):
        """Erro na conversa direta notifica e não propaga."""
        daemon = _daemon_with_mocks()
        daemon._engine.direct_agent_conversation.side_effect = RuntimeError("Erro")

        # Não deve lançar exceção
        await daemon._run_direct_agent("d1", "12345", "dev", "Texto")

        daemon._bus.notify.assert_called_once()
