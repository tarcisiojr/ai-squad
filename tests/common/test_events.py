"""Testes para ai_squad.common.events."""

from ai_squad.common.events import (
    EVENT_PROGRESS,
    EVENT_START_AGENT,
    CallbackRegistry,
)


class TestCallbackRegistry:
    def test_on_e_emit(self) -> None:
        registry = CallbackRegistry()
        resultados: list[str] = []

        registry.on("test", lambda msg: resultados.append(msg))
        registry.emit("test", "hello")

        assert resultados == ["hello"]

    def test_emit_evento_inexistente_retorna_none(self) -> None:
        registry = CallbackRegistry()
        resultado = registry.emit("nao_existe", "data")
        assert resultado is None

    def test_emit_com_kwargs(self) -> None:
        registry = CallbackRegistry()
        capturado: dict = {}

        def handler(**kwargs: object) -> None:
            capturado.update(kwargs)

        registry.on("test", handler)
        registry.emit("test", name="dev", task="build")

        assert capturado == {"name": "dev", "task": "build"}

    def test_substituicao_de_callback(self) -> None:
        registry = CallbackRegistry()
        resultados: list[int] = []

        registry.on("test", lambda: resultados.append(1))
        registry.emit("test")
        registry.on("test", lambda: resultados.append(2))
        registry.emit("test")

        assert resultados == [1, 2]

    def test_has_evento_registrado(self) -> None:
        registry = CallbackRegistry()
        assert not registry.has("test")

        registry.on("test", lambda: None)
        assert registry.has("test")

    def test_multiplos_eventos(self) -> None:
        registry = CallbackRegistry()
        resultados: list[str] = []

        registry.on("a", lambda: resultados.append("a"))
        registry.on("b", lambda: resultados.append("b"))

        registry.emit("a")
        registry.emit("b")
        registry.emit("a")

        assert resultados == ["a", "b", "a"]

    def test_emit_retorna_valor_do_callback(self) -> None:
        registry = CallbackRegistry()
        registry.on("calc", lambda x, y: x + y)

        resultado = registry.emit("calc", 2, 3)
        assert resultado == 5

    def test_constantes_de_eventos_sao_strings(self) -> None:
        assert isinstance(EVENT_PROGRESS, str)
        assert isinstance(EVENT_START_AGENT, str)

    def test_constantes_sao_unicas(self) -> None:
        from ai_squad.common import events

        nomes = [
            v for k, v in vars(events).items()
            if k.startswith("EVENT_") and isinstance(v, str)
        ]
        assert len(nomes) == len(set(nomes))
