"""Testes para roteamento de modelo por complexidade."""


from src.orchestrator.model_router import classify_complexity, select_model


class TestClassifyComplexity:
    """Testes para classificação de complexidade de mensagens."""

    def test_mensagem_curta_eh_light(self):
        """Mensagem muito curta deve ser light."""
        assert classify_complexity("oi") == "light"
        assert classify_complexity("status?") == "light"
        assert classify_complexity("ok") == "light"

    def test_mensagem_longa_eh_heavy(self):
        """Mensagem longa (>200 chars) deve ser heavy."""
        texto = "x" * 201
        assert classify_complexity(texto) == "heavy"

    def test_codigo_eh_heavy(self):
        """Mensagem com padrões de código deve ser heavy."""
        assert classify_complexity("def criar_usuario():") == "heavy"
        assert classify_complexity("class UserService:") == "heavy"
        assert classify_complexity("import json") == "heavy"
        assert classify_complexity("Use ```python para isso") == "heavy"

    def test_palavras_tecnicas_eh_heavy(self):
        """Mensagem com palavras-chave técnicas deve ser heavy."""
        assert classify_complexity("quero implementar um login") == "heavy"
        assert classify_complexity("pode criar um endpoint de API?") == "heavy"
        assert classify_complexity("preciso refatorar o módulo auth") == "heavy"
        assert classify_complexity("faça o merge dessa branch no main") == "heavy"

    def test_conversa_simples_eh_light(self):
        """Conversa simples sem palavras técnicas deve ser light."""
        assert classify_complexity("como vai você?") == "light"
        assert classify_complexity("o que estamos fazendo?") == "light"
        assert classify_complexity("tudo bem, valeu!") == "light"

    def test_multiplas_perguntas_eh_heavy(self):
        """Múltiplas interrogações indicam complexidade."""
        assert classify_complexity("qual o status? e o deploy? feito?") == "heavy"

    def test_delegacao_eh_heavy(self):
        """Referências a delegação de agentes deve ser heavy."""
        assert classify_complexity("delegar para o PO essa demanda") == "heavy"

    def test_string_vazia_eh_light(self):
        """String vazia deve ser light."""
        assert classify_complexity("") == "light"
        assert classify_complexity("   ") == "light"


class TestSelectModel:
    """Testes para seleção de modelo baseada em complexidade."""

    def test_sem_modelos_configurados_retorna_default(self):
        """Sem light/heavy, retorna modelo padrão."""
        result = select_model("oi", default_model="sonnet")
        assert result == "sonnet"

    def test_sem_modelos_e_sem_default_retorna_none(self):
        """Sem nenhuma configuração, retorna None."""
        result = select_model("oi")
        assert result is None

    def test_mensagem_simples_retorna_light(self):
        """Mensagem simples retorna modelo leve."""
        result = select_model("oi", light_model="haiku", heavy_model="sonnet")
        assert result == "haiku"

    def test_mensagem_complexa_retorna_heavy(self):
        """Mensagem complexa retorna modelo pesado."""
        result = select_model(
            "implementar autenticação OAuth2 no backend",
            light_model="haiku",
            heavy_model="sonnet",
        )
        assert result == "sonnet"

    def test_light_model_sem_heavy_retorna_default(self):
        """Apenas light_model configurado sem heavy retorna default."""
        result = select_model("oi", light_model="haiku", default_model="sonnet")
        assert result == "sonnet"

    def test_heavy_model_sem_light_retorna_default(self):
        """Apenas heavy_model configurado sem light retorna default."""
        result = select_model("oi", heavy_model="sonnet", default_model="haiku")
        assert result == "haiku"
