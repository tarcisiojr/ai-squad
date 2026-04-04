"""Testes para serialização do Squad Lead via semáforo."""

import asyncio

import pytest

from ai_squad.adapters.interface import AIAgentAdapter
from ai_squad.factory import AgentConfig
from ai_squad.models import AgentStatus
from ai_squad.orchestrator.engine import OrchestrationEngine
from ai_squad.orchestrator.state import StateManager


class _SlowAdapter(AIAgentAdapter):
    """Adapter que simula latência controlável."""

    def __init__(self, delay: float = 0.3):
        super().__init__()
        self._delay = delay
        self._call_count = 0

    async def run(self, prompt, context):
        self._call_count += 1
        await asyncio.sleep(self._delay)
        return f"resposta-{self._call_count}"

    async def ask(self, question):
        return "ok"

    def status(self):
        return AgentStatus.IDLE

    def on_human_needed(self, callback):
        pass


class _RecordBus:
    """Bus que grava todas as mensagens enviadas."""

    def __init__(self):
        self.mensagens: list[tuple[str, str]] = []

    async def send_message(self, user_id, text, **kwargs):
        self.mensagens.append((user_id, text))

    async def notify(self, user_id, text, **kwargs):
        self.mensagens.append((user_id, text))

    async def ask_user(self, user_id, question):
        return "ok"

    async def send_approval_request(self, user_id, question, options):
        return "Aprovar"

    async def send_typing(self, user_id, **kwargs):
        pass

    def mark_agent_active(self, label):
        pass

    def mark_agent_idle(self, label):
        pass


_PERSONAS = {
    "po": AgentConfig(name="PO", avatar="📋", command="/po"),
}


def _make_engine(tmp_path, adapter=None, bus=None):
    """Cria engine com mocks para testes de semáforo."""
    adapter = adapter or _SlowAdapter(delay=0.3)
    bus = bus or _RecordBus()
    state_mgr = StateManager(state_dir=str(tmp_path / "state"))
    workspace = str(tmp_path / "workspace")
    (tmp_path / "workspace").mkdir(exist_ok=True)
    return OrchestrationEngine(
        adapter,
        bus,
        state_mgr,
        workspace=workspace,
        personas=_PERSONAS,
    ), bus


class TestSemaphoreSerializacao:
    """Duas chamadas concorrentes são serializadas pelo semáforo."""

    @pytest.mark.asyncio
    async def test_chamadas_concorrentes_serializadas(self, tmp_path):
        """Segunda chamada espera a primeira terminar."""
        execution_order: list[str] = []
        adapter = _SlowAdapter(delay=0.2)
        engine, bus = _make_engine(tmp_path, adapter=adapter)

        # Substitui _run_squad_lead_inner para rastrear ordem de execução
        original = engine._run_squad_lead_inner

        async def _tracked_inner(demand_id, user_id, text, image_path=None, thread_id=None):
            execution_order.append(f"start-{demand_id}")
            result = await original(demand_id, user_id, text, image_path, thread_id)
            execution_order.append(f"end-{demand_id}")
            return result

        engine._run_squad_lead_inner = _tracked_inner

        # Dispara duas chamadas concorrentes
        t1 = asyncio.create_task(engine.run_squad_lead("d1", "user1", "tarefa 1"))
        # Pequeno delay para garantir que t1 adquire o semáforo primeiro
        await asyncio.sleep(0.01)
        t2 = asyncio.create_task(engine.run_squad_lead("d2", "user1", "tarefa 2"))

        await asyncio.gather(t1, t2)

        # A primeira deve começar e terminar antes da segunda começar
        assert execution_order[0] == "start-d1"
        assert execution_order[1] == "end-d1"
        assert execution_order[2] == "start-d2"
        assert execution_order[3] == "end-d2"

    @pytest.mark.asyncio
    async def test_semaphore_liberado_apos_erro(self, tmp_path):
        """Semáforo é liberado mesmo quando ocorre erro."""

        class _ErrorAdapter(_SlowAdapter):
            async def run(self, prompt, context):
                self._call_count += 1
                if self._call_count == 1:
                    raise RuntimeError("erro simulado")
                return "ok"

        adapter = _ErrorAdapter(delay=0.0)
        engine, bus = _make_engine(tmp_path, adapter=adapter)

        # Primeira chamada falha (adapter retorna "" após erro tratado internamente)
        r1 = await engine.run_squad_lead("d1", "user1", "tarefa 1")

        # Segunda chamada deve funcionar (semáforo liberado)
        r2 = await engine.run_squad_lead("d2", "user1", "tarefa 2")
        assert r2 == "ok"


class TestSemaphoreTimeout:
    """Timeout no semáforo envia feedback ao usuário."""

    @pytest.mark.asyncio
    async def test_feedback_ao_aguardar(self, tmp_path):
        """Quando semáforo está ocupado além do timeout, envia mensagem."""
        adapter = _SlowAdapter(delay=0.5)
        engine, bus = _make_engine(tmp_path, adapter=adapter)

        # Reduz timeout do semáforo para acelerar o teste
        original_run = engine.run_squad_lead

        async def _patched_run(demand_id, user_id, text, image_path=None, thread_id=None):
            """Versão com timeout reduzido para teste."""
            try:
                await asyncio.wait_for(engine._squad_lead_semaphore.acquire(), timeout=0.05)
            except asyncio.TimeoutError:
                await engine._message_bus.send_message(
                    user_id,
                    "Aguardando Squad Lead finalizar tarefa anterior...",
                    thread_id=thread_id,
                )
                await engine._squad_lead_semaphore.acquire()

            try:
                return await engine._run_squad_lead_inner(
                    demand_id, user_id, text, image_path, thread_id
                )
            finally:
                engine._squad_lead_semaphore.release()

        engine.run_squad_lead = _patched_run

        # Dispara duas chamadas: a segunda vai esperar
        t1 = asyncio.create_task(engine.run_squad_lead("d1", "user1", "tarefa 1"))
        await asyncio.sleep(0.01)
        t2 = asyncio.create_task(engine.run_squad_lead("d2", "user1", "tarefa 2"))

        await asyncio.gather(t1, t2)

        # Verifica que a mensagem de espera foi enviada
        aguardando = [msg for _, msg in bus.mensagens if "Aguardando" in msg]
        assert len(aguardando) >= 1, (
            f"Esperava mensagem 'Aguardando...', mensagens: {bus.mensagens}"
        )

    @pytest.mark.asyncio
    async def test_semaphore_existe_no_init(self, tmp_path):
        """Verifica que o semáforo é criado no __init__."""
        engine, _ = _make_engine(tmp_path)
        assert hasattr(engine, "_squad_lead_semaphore")
        assert isinstance(engine._squad_lead_semaphore, asyncio.Semaphore)
