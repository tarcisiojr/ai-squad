"""Testes para o sistema de heartbeat — retomada de demandas paradas."""

import json
from datetime import datetime, timezone, timedelta

import pytest

from src.factory import HeartbeatConfig
from src.orchestrator.journal import JournalStore


class TestHeartbeatDetection:
    """Testes de detecção de demandas paradas via JournalStore."""

    @pytest.fixture
    def store(self, tmp_path):
        return JournalStore(state_dir=str(tmp_path))

    def _age_journal(self, store, demand_id, hours):
        """Envelhece um journal simulando updated_at no passado."""
        journal = store.read(demand_id)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        journal["updated_at"] = old_time
        path = store._journal_path(demand_id)
        with open(path, "w") as f:
            json.dump(journal, f)

    def test_detecta_demanda_dev_parada(self, store):
        """Detecta demanda em dev_working parada há mais de 30 min."""
        store.create("d1", "Feature login")
        store.set_phase("d1", "dev_working")
        self._age_journal(store, "d1", hours=1)

        stalled = store.get_stalled(stall_timeout=1800)
        assert len(stalled) == 1
        assert stalled[0]["demand_id"] == "d1"

    def test_nao_detecta_approval_como_parada(self, store):
        """Demandas em awaiting_*_approval NÃO são paradas."""
        store.create("d2", "Feature signup")
        store.set_phase("d2", "awaiting_plan_approval")
        self._age_journal(store, "d2", hours=2)

        stalled = store.get_stalled(stall_timeout=1800)
        assert len(stalled) == 0

    def test_detecta_pending_approval(self, store):
        """Detecta aprovação pendente há mais de 1h para lembrete."""
        store.create("d3", "Feature dashboard")
        store.set_phase("d3", "awaiting_plan_approval")
        self._age_journal(store, "d3", hours=2)

        pending = store.get_pending_approvals(reminder_timeout=3600)
        assert len(pending) == 1
        assert pending[0]["demand_id"] == "d3"

    def test_nao_detecta_demanda_recente(self, store):
        """Demanda atualizada há pouco NÃO é parada."""
        store.create("d4", "Feature recente")
        store.set_phase("d4", "dev_working")
        # Sem envelhecer — acabou de ser criada

        stalled = store.get_stalled(stall_timeout=1800)
        assert len(stalled) == 0

    def test_max_retries_registrado(self, store):
        """Verifica que retries são incrementados corretamente."""
        store.create("d5", "Feature retry")
        store.increment_retries("d5")
        store.increment_retries("d5")
        store.increment_retries("d5")

        journal = store.read("d5")
        assert journal["auto_retries"] == 3

    def test_multiplas_demandas_paradas(self, store):
        """Detecta múltiplas demandas paradas simultaneamente."""
        store.create("d6", "Feature A")
        store.set_phase("d6", "po_working")
        self._age_journal(store, "d6", hours=1)

        store.create("d7", "Feature B")
        store.set_phase("d7", "qa_validating")
        self._age_journal(store, "d7", hours=2)

        store.create("d8", "Feature C")
        store.set_phase("d8", "dev_working")
        # d8 é recente — não deve aparecer

        stalled = store.get_stalled(stall_timeout=1800)
        assert len(stalled) == 2
        ids = {s["demand_id"] for s in stalled}
        assert "d6" in ids
        assert "d7" in ids
        assert "d8" not in ids


class TestHeartbeatConfig:
    """Testes da configuração de heartbeat."""

    def test_config_defaults(self):
        """Verifica valores default da config."""
        config = HeartbeatConfig()
        assert config.enabled is True
        assert config.interval == 300
        assert config.stall_timeout == 1800
        assert config.reminder_timeout == 3600
        assert config.max_auto_retries == 3

    def test_config_custom(self):
        """Verifica config customizada."""
        config = HeartbeatConfig(
            enabled=False,
            interval=60,
            stall_timeout=600,
            reminder_timeout=1800,
            max_auto_retries=5,
        )
        assert config.enabled is False
        assert config.interval == 60
        assert config.stall_timeout == 600

    def test_config_from_yaml(self, tmp_path):
        """Verifica carregamento de heartbeat do YAML."""
        import yaml
        from src.factory import PlatformConfig

        config_file = tmp_path / "platform.yaml"
        config_file.write_text(yaml.dump({
            "ai_provider": "mock",
            "messaging_provider": "cli",
            "heartbeat": {
                "enabled": True,
                "interval": 120,
                "stall_timeout": 900,
            },
        }))

        config = PlatformConfig.from_yaml(config_file)
        assert config.heartbeat.enabled is True
        assert config.heartbeat.interval == 120
        assert config.heartbeat.stall_timeout == 900
        # Valores não especificados usam default
        assert config.heartbeat.reminder_timeout == 3600
        assert config.heartbeat.max_auto_retries == 3
