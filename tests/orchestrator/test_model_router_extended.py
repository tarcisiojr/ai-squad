"""Testes adicionais para model_router — resolve_model_for_tier e edge cases."""

from ai_squad.orchestrator.model_router import (
    classify_complexity,
    resolve_model_for_tier,
    select_model,
)


class TestResolveModelForTier:
    """Testes para resolve_model_for_tier."""

    def test_fast_com_light_model(self):
        """Tier 'fast' retorna light_model."""
        result = resolve_model_for_tier("fast", light_model="haiku", heavy_model="sonnet")
        assert result == "haiku"

    def test_powerful_com_heavy_model(self):
        """Tier 'powerful' retorna heavy_model."""
        result = resolve_model_for_tier("powerful", light_model="haiku", heavy_model="sonnet")
        assert result == "sonnet"

    def test_fast_sem_light_model_retorna_default(self):
        """Tier 'fast' sem light_model retorna default_model."""
        result = resolve_model_for_tier("fast", heavy_model="sonnet", default_model="claude")
        assert result == "claude"

    def test_powerful_sem_heavy_model_retorna_default(self):
        """Tier 'powerful' sem heavy_model retorna default_model."""
        result = resolve_model_for_tier("powerful", light_model="haiku", default_model="claude")
        assert result == "claude"

    def test_tier_desconhecido_retorna_default(self):
        """Tier desconhecido retorna default_model."""
        result = resolve_model_for_tier(
            "unknown", light_model="haiku", heavy_model="sonnet", default_model="claude"
        )
        assert result == "claude"

    def test_sem_modelos_retorna_none(self):
        """Sem nenhum modelo configurado retorna None."""
        result = resolve_model_for_tier("fast")
        assert result is None

    def test_tier_vazio_retorna_default(self):
        """Tier vazio retorna default_model."""
        result = resolve_model_for_tier("", default_model="claude")
        assert result == "claude"


class TestClassifyComplexityEdgeCases:
    """Testes edge cases para classify_complexity."""

    def test_arrow_functions(self):
        """Texto com arrows (=>, ->) é heavy."""
        assert classify_complexity("use x => x + 1 pattern") == "heavy"

    def test_method_calls(self):
        """Texto com chamadas de método é heavy."""
        assert classify_complexity("chame user.getName() aqui") == "heavy"

    def test_multilinhas(self):
        """Texto com muitas linhas é heavy."""
        text = "linha1\nlinha2\nlinha3\nlinha4\nlinha5"
        assert classify_complexity(text) == "heavy"

    def test_mensagem_media_sem_keywords(self):
        """Mensagem de tamanho médio sem keywords é light."""
        assert classify_complexity("como voce esta hoje?") == "light"

    def test_spec_keyword(self):
        """Palavra-chave 'spec' classifica como heavy."""
        assert classify_complexity("preciso criar uma spec") == "heavy"

    def test_openspec_keyword(self):
        """Palavra-chave 'openspec' classifica como heavy."""
        assert classify_complexity("use openspec para planejar") == "heavy"


class TestSelectModelEdgeCases:
    """Testes edge cases para select_model."""

    def test_apenas_light_model_retorna_default(self):
        """Apenas light_model sem heavy retorna default."""
        result = select_model("oi", light_model="haiku")
        assert result is None

    def test_apenas_heavy_model_retorna_default(self):
        """Apenas heavy_model sem light retorna default."""
        result = select_model("oi", heavy_model="sonnet")
        assert result is None

    def test_mensagem_complexa_com_codigo(self):
        """Mensagem com código retorna heavy."""
        result = select_model(
            "def criar():\n    pass",
            light_model="haiku",
            heavy_model="sonnet",
        )
        assert result == "sonnet"
