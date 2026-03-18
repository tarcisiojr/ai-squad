"""Testes para notas diárias."""

from datetime import date, timedelta

from src.orchestrator.daily_notes import DailyNotes


class TestDailyNotes:
    """Testes para DailyNotes."""

    def test_adicionar_entrada(self, tmp_path):
        """Verifica adição de entrada na nota do dia."""
        notes = DailyNotes(state_dir=str(tmp_path))
        today = date.today()

        notes.add_entry("Teste de entrada", day=today)
        content = notes.load_day(today)

        assert "Teste de entrada" in content
        assert today.isoformat() in content

    def test_multiplas_entradas_acumulam(self, tmp_path):
        """Verifica que entradas se acumulam no mesmo dia."""
        notes = DailyNotes(state_dir=str(tmp_path))
        today = date.today()

        notes.add_entry("Entrada 1", day=today)
        notes.add_entry("Entrada 2", day=today)
        content = notes.load_day(today)

        assert "Entrada 1" in content
        assert "Entrada 2" in content

    def test_dias_diferentes_separados(self, tmp_path):
        """Verifica que dias diferentes ficam em arquivos separados."""
        notes = DailyNotes(state_dir=str(tmp_path))
        today = date.today()
        yesterday = today - timedelta(days=1)

        notes.add_entry("Hoje", day=today)
        notes.add_entry("Ontem", day=yesterday)

        assert "Hoje" in notes.load_day(today)
        assert "Ontem" in notes.load_day(yesterday)
        assert "Ontem" not in notes.load_day(today)

    def test_load_day_inexistente(self, tmp_path):
        """Verifica retorno vazio para dia sem notas."""
        notes = DailyNotes(state_dir=str(tmp_path))
        assert notes.load_day(date.today()) == ""

    def test_add_demand_completed(self, tmp_path):
        """Verifica registro de demanda concluída."""
        notes = DailyNotes(state_dir=str(tmp_path))
        today = date.today()

        notes.add_demand_completed("d-001", "Criar landing page", day=today)
        content = notes.load_day(today)

        assert "d-001" in content
        assert "Criar landing page" in content
        assert "Demanda concluída" in content

    def test_add_agent_event(self, tmp_path):
        """Verifica registro de evento de agente."""
        notes = DailyNotes(state_dir=str(tmp_path))
        today = date.today()

        notes.add_agent_event("dev-backend", "Concluiu com sucesso", day=today)
        content = notes.load_day(today)

        assert "dev-backend" in content
        assert "Concluiu com sucesso" in content

    def test_load_recent_sem_notas(self, tmp_path):
        """Verifica retorno vazio quando não há notas recentes."""
        notes = DailyNotes(state_dir=str(tmp_path))
        assert notes.load_recent() == ""

    def test_load_recent_com_notas(self, tmp_path):
        """Verifica carregamento de notas recentes."""
        notes = DailyNotes(state_dir=str(tmp_path))
        today = date.today()
        yesterday = today - timedelta(days=1)

        notes.add_entry("Atividade de hoje", day=today)
        notes.add_entry("Atividade de ontem", day=yesterday)

        recent = notes.load_recent(days=3)

        assert "Notas recentes" in recent
        assert "Atividade de hoje" in recent
        assert "Atividade de ontem" in recent

    def test_load_recent_nao_inclui_dias_antigos(self, tmp_path):
        """Verifica que dias muito antigos não são incluídos."""
        notes = DailyNotes(state_dir=str(tmp_path))
        old_day = date.today() - timedelta(days=10)

        notes.add_entry("Muito antigo", day=old_day)

        recent = notes.load_recent(days=3)
        assert recent == ""  # não tem notas nos últimos 3 dias

    def test_escrita_atomica(self, tmp_path):
        """Verifica que não existem arquivos .tmp após escrita."""
        notes = DailyNotes(state_dir=str(tmp_path))
        notes.add_entry("teste")

        tmp_files = list((tmp_path / "daily").rglob("*.tmp"))
        assert len(tmp_files) == 0

    def test_diretorio_criado_automaticamente(self, tmp_path):
        """Verifica que diretório daily é criado automaticamente."""
        notes = DailyNotes(state_dir=str(tmp_path))
        assert (tmp_path / "daily").exists()
