"""Módulo de carregamento básico de arquivos binários.

Este módulo fornece funcionalidades para ler arquivos em modo binário,
não modificando o arquivo original e sem realizar parsing específico.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class SaveLoadResult(NamedTuple):
    """Resultado da tentativa de carregar um save."""

    path: str
    success: bool
    error_message: str | None = None
    size_bytes: int | None = None
    data: bytes | None = None


def load_save(save_path: str | Path) -> SaveLoadResult:
    """Carrega o arquivo de save em modo binário (apenas leitura).

    Este método lê o conteúdo do arquivo de save sem modificar o original.
    O arquivo é lido completamente para memória como bytes e nunca salvo.

    Args:
        save_path: Caminho do arquivo de save (str ou Path).

    Returns:
        SaveLoadResult com informações sobre a leitura:
        - path: caminho normalizado do arquivo
        - success: True se o arquivo foi lido com sucesso
        - error_message: mensagem de erro, None se sucesso
        - size_bytes: tamanho em bytes do arquivo
        - data: conteúdo binário do arquivo (apenas leitura)
    """
    path = Path(save_path)

    # Normaliza o caminho para string absoluta
    abs_path = str(path.resolve())

    # Validação básica do tipo de arquivo
    if not path.is_file():
        return SaveLoadResult(
            path=abs_path,
            success=False,
            error_message="Caminho apontado nao eh um arquivo valido."
        )

    try:
        # Lê o arquivo exclusivamente em modo binário (apenas leitura)
        with open(abs_path, "rb") as f:
            data = f.read()
            size = len(data)

            # Validação de tamanho mínimo
            if size < 1:
                raise ValueError("O arquivo está vazio ou menor que o tamanho mínimo esperado (>= 1 byte).")

            return SaveLoadResult(
                path=abs_path,
                success=True,
                error_message=None,
                size_bytes=size,
                data=data
            )

    except FileNotFoundError:
        return SaveLoadResult(
            path=abs_path,
            success=False,
            error_message="Arquivo nao foi encontrado."
        )

    except PermissionError:
        return SaveLoadResult(
            path=abs_path,
            success=False,
            error_message="Sem permissoes para ler o arquivo."
        )

    except ValueError as e:
        return SaveLoadResult(
            path=abs_path,
            success=False,
            error_message=str(e)
        )


def validate_save_file(save_path: str | Path) -> tuple[bool, str | None]:
    """Valida se um arquivo parece ser um save válido (verificação básica).

    Args:
        save_path: Caminho do arquivo de save.

    Returns:
        Tupla (is_valid, error_message):
        - True se o arquivo parece válido
        - False + mensagem de erro caso contrário
    """
    result = load_save(save_path)

    if result.success:
        return True, None
    else:
        return False, result.error_message or "Erro desconhecido ao validar save."