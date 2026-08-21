"""Entrada de ponto principal para execução com python -m mr_farmboy_manager."""

import sys
from .qml_application import run


def main() -> int:
    """Executa a aplicação PySide6.

    Returns:
        Código de saída da aplicação (0 para sucesso).
    """
    return run()


if __name__ == "__main__":
    sys.exit(main())
