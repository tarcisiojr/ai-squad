"""Testes de integração do preset helpdesk.

Verifica fluxos completos: chamado → busca → resposta → reação → score,
ingestão de documentos e integração entre componentes.
"""

import pytest

from ai_squad.orchestrator.ingest import DocumentIngest
from ai_squad.orchestrator.knowledge import KnowledgeStore, parse_frontmatter
from ai_squad.orchestrator.reaction_tracker import ReactionTracker


class TestHelpdeskFluxoCompleto:
    """Testa o fluxo completo de atendimento."""

    @pytest.fixture
    def kb_dir(self, tmp_path):
        """Cria knowledge base com documentos de teste."""
        kb = tmp_path / "knowledge"
        kb.mkdir()
        atendimentos = kb / "atendimentos"
        atendimentos.mkdir()

        # Documento pré-existente
        (atendimentos / "vpn-nao-conecta.md").write_text(
            "---\nscore: 3\ntags: [vpn, rede, forticlient]\ncreated: 2026-03-10\n"
            "source: atendimento\n---\n"
            "# VPN não conecta\n\n"
            "## Problema\nVPN parou de funcionar após atualização.\n\n"
            "## Solução\n1. Reiniciar FortiClient\n2. Limpar cache DNS\n",
            encoding="utf-8",
        )
        return kb

    @pytest.fixture
    def store(self, kb_dir):
        """KnowledgeStore com documentos indexados."""
        s = KnowledgeStore(kb_dir)
        s.reindex_all()
        yield s
        s.close()

    @pytest.fixture
    def tracker(self, store):
        """ReactionTracker conectado ao knowledge store."""
        return ReactionTracker(knowledge_store=store)

    @pytest.fixture
    def ingest(self, kb_dir):
        """DocumentIngest para a mesma knowledge base."""
        return DocumentIngest(kb_dir)

    def test_fluxo_chamado_com_solucao_na_kb(self, store, tracker):
        """Chamado → busca KB → encontra → responde → reação 👍 → score sobe."""
        # 1. Busca na KB
        results = store.search("VPN não funciona")
        assert len(results) >= 1
        assert "vpn" in results[0].path

        # 2. Simula resposta usando o documento (msg_id 100)
        doc_path = results[0].path
        tracker.track(100, doc_path)

        # 3. Usuário reage 👍
        updated = tracker.on_reaction(100, "👍")
        assert updated == doc_path

        # 4. Score deve ter subido
        results = store.search("VPN")
        vpn_doc = [r for r in results if "vpn" in r.path][0]
        assert vpn_doc.score == 4  # Era 3, +1

    def test_fluxo_chamado_sem_solucao_registra_novo(self, store, ingest, kb_dir):
        """Chamado → busca KB → não encontra → resolve → registra novo .md."""
        # 1. Busca na KB — não encontra
        results = store.search("impressora 3 andar")
        assert len(results) == 0

        # 2. Atendente resolve e registra
        path = ingest.ingest_text(
            text="## Problema\nImpressora do 3º andar não imprime.\n\n"
            "## Solução\nReiniciar spooler de impressão.\n",
            title="Impressora 3º andar",
            category="atendimentos",
        )
        assert path is not None

        # 3. Indexa o novo documento
        store.index(path)

        # 4. Agora deve encontrar
        results = store.search("impressora andar")
        assert len(results) >= 1

    def test_fluxo_ingestao_documento(self, store, ingest, kb_dir, tmp_path):
        """Documento enviado → converte → indexa → busca funciona."""
        # 1. Cria arquivo de texto simulando envio pelo Telegram
        doc = tmp_path / "processo-onboarding.md"
        doc.write_text(
            "# Processo de Onboarding\n\n"
            "## Etapas\n1. Criar conta AD\n2. Solicitar VPN\n3. Configurar email\n\n"
            "## Responsável\nRH + TI\n",
            encoding="utf-8",
        )

        # 2. Ingere documento
        result = ingest.ingest(doc, category="processos")
        assert result is not None

        # 3. Indexa
        store.index(result)

        # 4. Busca deve encontrar
        results = store.search("onboarding conta")
        assert len(results) >= 1

    def test_fluxo_reacao_negativa_decrementa_score(self, store, tracker, kb_dir):
        """Reação 👎 decrementa score do documento."""
        results = store.search("VPN")
        doc_path = results[0].path
        score_inicial = results[0].score

        tracker.track(200, doc_path)
        tracker.on_reaction(200, "👎")

        results = store.search("VPN")
        vpn_doc = [r for r in results if "vpn" in r.path][0]
        assert vpn_doc.score == score_inicial - 1

    def test_fluxo_multiplas_reacoes_acumulam(self, store, tracker):
        """Múltiplas reações acumulam score."""
        results = store.search("VPN")
        doc_path = results[0].path

        # 3 reações positivas
        for msg_id in [301, 302, 303]:
            tracker.track(msg_id, doc_path)
            tracker.on_reaction(msg_id, "👍")

        results = store.search("VPN")
        vpn_doc = [r for r in results if "vpn" in r.path][0]
        assert vpn_doc.score == 6  # Era 3, +3

    def test_frontmatter_persistido_apos_reacao(self, store, tracker, kb_dir):
        """Score atualizado é persistido no frontmatter do .md."""
        results = store.search("VPN")
        doc_path = results[0].path
        tracker.track(400, doc_path)
        tracker.on_reaction(400, "👍")

        # Lê o arquivo direto e verifica frontmatter
        full_path = kb_dir / doc_path
        content = full_path.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)
        assert meta["score"] == 4  # Era 3, +1


class TestHelpdeskPresetStructure:
    """Verifica que a estrutura do preset está correta."""

    def test_pipeline_yaml_existe(self):
        """Verifica que pipeline.yaml do helpdesk existe."""
        from pathlib import Path

        pipeline = Path("ai_squad/presets/helpdesk/pipeline/pipeline.yaml")
        assert pipeline.exists()

    def test_pipeline_yaml_valido(self):
        """Verifica que pipeline.yaml é YAML válido com steps."""
        from pathlib import Path

        import yaml

        pipeline = Path("ai_squad/presets/helpdesk/pipeline/pipeline.yaml")
        data = yaml.safe_load(pipeline.read_text(encoding="utf-8"))
        assert data["name"] == "Helpdesk"
        assert "pipeline" in data
        steps = data["pipeline"]["steps"]
        assert len(steps) == 3
        step_ids = [s["id"] for s in steps]
        assert "atendimento" in step_ids
        assert "escalacao" in step_ids
        assert "registro" in step_ids

    def test_agents_md_existem(self):
        """Verifica que todos os AGENTS.md do helpdesk existem."""
        from pathlib import Path

        agents = ["squad-lead", "atendente", "base-conhecimento"]
        for agent in agents:
            path = Path(f"ai_squad/presets/helpdesk/agents/{agent}/AGENTS.md")
            assert path.exists(), f"AGENTS.md não encontrado: {agent}"

    def test_steps_md_existem(self):
        """Verifica que todos os steps .md existem."""
        from pathlib import Path

        steps = [
            "steps/step-01-atendimento.md",
            "steps/step-02-escalacao.md",
            "steps/step-03-registro.md",
        ]
        for step in steps:
            path = Path(f"ai_squad/presets/helpdesk/pipeline/{step}")
            assert path.exists(), f"Step não encontrado: {step}"

    def test_knowledge_dirs_existem(self):
        """Verifica que diretórios da knowledge base existem."""
        from pathlib import Path

        dirs = [
            "knowledge/atendimentos",
            "knowledge/documentacao/sistemas",
            "knowledge/documentacao/processos",
            "knowledge/documentacao/faq",
        ]
        for d in dirs:
            path = Path(f"ai_squad/presets/helpdesk/{d}")
            assert path.exists(), f"Diretório não encontrado: {d}"


class TestTeamManagerHelpdeskPreset:
    """Verifica que o TeamManager copia o preset helpdesk corretamente."""

    def test_create_local_com_preset_helpdesk(self, tmp_path):
        """Verifica que create_local copia agents, pipeline e knowledge."""
        from ai_squad.cli.team_manager import TeamManager

        manager = TeamManager(base_dir=tmp_path / ".ai-squad")
        squad_dir = manager.create_local("test", project_dir=tmp_path, preset="helpdesk")

        assert (squad_dir / "agents" / "atendente" / "AGENTS.md").exists()
        assert (squad_dir / "agents" / "base-conhecimento" / "AGENTS.md").exists()
        assert (squad_dir / "agents" / "squad-lead" / "AGENTS.md").exists()
        assert (squad_dir / "pipeline" / "pipeline.yaml").exists()
        assert (squad_dir / "knowledge" / "atendimentos").exists()
        assert (squad_dir / "knowledge" / "documentacao" / "sistemas").exists()
