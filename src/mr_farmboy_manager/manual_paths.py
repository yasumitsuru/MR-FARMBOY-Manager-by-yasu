"""Módulo de backend para validação e carregamento manual de caminhos."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from mr_farmboy_manager.save_slots import build_save_slot_summaries, SaveSlotSummary


class DirectoryValidationCode(StrEnum):
    """Códigos de status de validação de diretório."""

    VALID = "valid"
    EMPTY = "empty"
    NOT_FOUND = "not_found"
    NOT_DIRECTORY = "not_directory"


@dataclass(frozen=True, slots=True)
class DirectoryValidationResult:
    """Resultado da validação de um caminho de diretório.

    Attributes:
        code: Código de status da validação.
        path: Caminho normalizado (apenas quando não é vazio).
    """

    code: DirectoryValidationCode
    path: Path | None

    @property
    def is_valid(self) -> bool:
        """Retorna True somente para VALID."""
        return self.code == DirectoryValidationCode.VALID


def validate_directory_path(
    value: Path | str | None,
) -> DirectoryValidationResult:
    """Valida um caminho de diretório fornecido.

    Args:
        value: Caminho a validar (Path, str ou None).

    Returns:
        DirectoryValidationResult com o código de status e caminho normalizado.
    """
    # Valor vazio
    if value is None or value == "":
        return DirectoryValidationResult(
            code=DirectoryValidationCode.EMPTY,
            path=None,
        )

    # Converter para string para verificar espaços em branco
    if isinstance(value, str) and value.strip() == "":
        return DirectoryValidationResult(
            code=DirectoryValidationCode.EMPTY,
            path=None,
        )

    # Converter para Path e expandir ~
    path = Path(value).expanduser()

    # Caminho inexistente
    if not path.exists():
        return DirectoryValidationResult(
            code=DirectoryValidationCode.NOT_FOUND,
            path=path,
        )

    # Arquivo existente (não é diretório)
    if not path.is_dir():
        return DirectoryValidationResult(
            code=DirectoryValidationCode.NOT_DIRECTORY,
            path=path,
        )

    # Diretório válido
    return DirectoryValidationResult(
        code=DirectoryValidationCode.VALID,
        path=path,
    )


@dataclass(frozen=True, slots=True)
class SaveSlotsLoadResult:
    """Resultado do carregamento de slots de save.

    Attributes:
        validation: Resultado da validação do diretório.
        summaries: Tupla de resumos dos slots (vazia se nenhum slot encontrado).
    """

    validation: DirectoryValidationResult
    summaries: tuple[SaveSlotSummary, ...]

    @property
    def is_success(self) -> bool:
        """Retorna True quando a validação é válida."""
        return self.validation.is_valid


def load_save_slot_summaries(
    save_path: Path | str | None,
) -> SaveSlotsLoadResult:
    """Carrega resumos de slots de save a partir de um caminho manual.

    Args:
        save_path: Caminho do diretório dos saves (Path, str ou None).

    Returns:
        SaveSlotsLoadResult com validação e resumos.
    """
    # 1. Validar o caminho
    validation = validate_directory_path(save_path)

    # 2. Se inválido, retornar sem chamar build_save_slot_summaries
    if not validation.is_valid:
        return SaveSlotsLoadResult(
            validation=validation,
            summaries=(),
        )

    # 3. Se válido, chamar build_save_slot_summaries
    summaries_list = build_save_slot_summaries(base_path=validation.path)

    # 4. Converter lista para tupla
    # 5. Preservar ordem e objetos
    return SaveSlotsLoadResult(
        validation=validation,
        summaries=tuple(summaries_list),
    )
