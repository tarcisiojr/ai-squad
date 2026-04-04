"""Testes para build_prompt do adapters/prompt_builder.py."""

from ai_squad.adapters.prompt_builder import build_prompt


class TestBuildPrompt:
    """Testes para a funcao build_prompt."""

    def test_prompt_simples_sem_contexto(self):
        """Prompt sem contexto retorna apenas o prompt original."""
        result = build_prompt("Implemente o login", {})
        assert result == "Implemente o login"

    def test_com_workspace_context(self):
        """Verifica que workspace_context e adicionado como secao."""
        context = {"workspace_context": "Projeto Flask com SQLAlchemy"}
        result = build_prompt("Crie a API", context)

        assert "## Contexto do Projeto" in result
        assert "Projeto Flask com SQLAlchemy" in result
        assert "Crie a API" in result
        # workspace_context deve ser consumido (pop)
        assert "workspace_context" not in context

    def test_com_system_instructions(self):
        """Verifica que system_instructions e adicionado."""
        context = {"system_instructions": "Voce e um agente PO."}
        result = build_prompt("Escreva specs", context)

        assert "Voce e um agente PO." in result
        assert "Escreva specs" in result
        assert "system_instructions" not in context

    def test_com_contexto_adicional(self):
        """Verifica que campos extras sao listados na secao Contexto."""
        context = {
            "step": "review",
            "pipeline": "dev-openspec",
        }
        result = build_prompt("Revise o codigo", context)

        assert "## Contexto" in result
        assert "- step: review" in result
        assert "- pipeline: dev-openspec" in result
        assert "Revise o codigo" in result

    def test_filtra_chaves_internas(self):
        """Verifica que chaves internas sao filtradas do contexto."""
        context = {
            "demand_id": "abc123",
            "agent_name": "po",
            "fase": "planejamento",
            "max_turns": 10,
            "step": "review",
        }
        result = build_prompt("Tarefa", context)

        # Chaves internas nao devem aparecer
        assert "demand_id" not in result
        assert "agent_name" not in result
        assert "fase" not in result
        assert "max_turns" not in result
        # Chave nao-interna deve aparecer
        assert "- step: review" in result

    def test_completo_com_todas_secoes(self):
        """Verifica prompt completo com todas as secoes."""
        context = {
            "workspace_context": "Projeto React + Node",
            "system_instructions": "Voce e o dev backend.",
            "tecnologias": "TypeScript, Express",
        }
        result = build_prompt("Implemente endpoint de auth", context)

        # Verifica que todas as secoes estao presentes
        assert "## Contexto do Projeto" in result
        assert "Voce e o dev backend." in result
        assert "## Contexto" in result
        assert "Implemente endpoint de auth" in result

        # Verifica ordem: projeto antes de instructions, prompt no final
        idx_projeto = result.index("## Contexto do Projeto")
        idx_instructions = result.index("Voce e o dev backend.")
        idx_prompt = result.index("Implemente endpoint de auth")

        assert idx_projeto < idx_instructions < idx_prompt

    def test_context_pop_nao_afeta_chaves_extras(self):
        """Verifica que pop de chaves especiais nao afeta chaves extras."""
        context = {
            "workspace_context": "ctx",
            "system_instructions": "instr",
            "extra": "valor",
        }
        build_prompt("prompt", context)

        # Chaves especiais foram removidas
        assert "workspace_context" not in context
        assert "system_instructions" not in context
        # Chave extra permanece
        assert "extra" in context

    def test_sem_display_context_nao_adiciona_secao(self):
        """Sem chaves extras (alem das internas), nao adiciona secao Contexto."""
        context = {
            "demand_id": "abc",
            "agent_name": "po",
        }
        result = build_prompt("Tarefa", context)

        assert "## Contexto" not in result
        assert "Tarefa" in result

    def test_prompt_vazio(self):
        """Prompt vazio funciona."""
        result = build_prompt("", {})
        assert result == ""

    def test_workspace_context_vazio_nao_adiciona(self):
        """workspace_context vazio (string vazia) nao adiciona secao."""
        context = {"workspace_context": ""}
        result = build_prompt("Tarefa", context)
        assert "## Contexto do Projeto" not in result

    def test_system_instructions_vazio_nao_adiciona(self):
        """system_instructions vazio nao adiciona secao."""
        context = {"system_instructions": ""}
        result = build_prompt("Tarefa", context)
        # system_instructions vazio (falsy) nao e adicionado
        assert result == "Tarefa"
