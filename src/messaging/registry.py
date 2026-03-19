"""Registry de providers de mensageria.

Cada provider se registra aqui ao ser importado.
O daemon usa o registry para resolver o provider pelo nome da config.
"""

from src.messaging.interface import MessageBus

# Mapeamento nome → classe concreta
_PROVIDERS: dict[str, type[MessageBus]] = {}


def register(name: str, cls: type[MessageBus]) -> None:
    """Registra um provider de mensageria pelo nome."""
    _PROVIDERS[name] = cls


def get(name: str) -> type[MessageBus]:
    """Retorna a classe do provider pelo nome. Erro se não registrado."""
    if name not in _PROVIDERS:
        available = ", ".join(sorted(_PROVIDERS.keys())) or "(nenhum)"
        raise ValueError(
            f"Provider de mensageria não registrado: '{name}'. Disponíveis: {available}"
        )
    return _PROVIDERS[name]


def available() -> list[str]:
    """Retorna nomes dos providers registrados."""
    return sorted(_PROVIDERS.keys())


def load_builtin_providers() -> None:
    """Importa providers builtin para que se auto-registrem.

    Chamado pelo daemon/CLI antes de resolver o provider.
    Imports protegidos para não falhar se dependência opcional não instalada.
    """
    # Telegram — dependência opcional: python-telegram-bot
    try:
        import src.messaging.telegram  # noqa: F401
    except ImportError:
        pass

    # CLI — sempre disponível
    try:
        import src.messaging.cli  # noqa: F401
    except ImportError:
        pass

    # Google Chat — dependência opcional: google-auth, google-api-python-client
    try:
        import src.messaging.gchat  # noqa: F401
    except ImportError:
        pass
