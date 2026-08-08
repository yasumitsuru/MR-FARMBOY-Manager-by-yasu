"""Contratos puros para identificação e localização segura de backups."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from .save_slots import SaveSlot


class BackupErrorCode(str, Enum):
    """Códigos estáveis para a apresentação de erros pela interface."""

    INVALID_SLOT = "invalid_slot"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_SUFFIX = "invalid_suffix"
    INVALID_BACKUP_ID = "invalid_backup_id"
    INCOHERENT_SOURCE = "incoherent_source"
    UNSAFE_BACKUP_ROOT = "unsafe_backup_root"
    SOURCE_INSIDE_BACKUP_ROOT = "source_inside_backup_root"
    DESTINATION_OUTSIDE_BACKUP_ROOT = "destination_outside_backup_root"


class BackupValidationError(ValueError):
    """Erro de validação com texto seguro para exibição ao usuário."""

    def __init__(self, code: BackupErrorCode, public_message: str) -> None:
        self.code = code
        self.public_message = public_message
        super().__init__(public_message)


@dataclass(frozen=True, slots=True)
class BackupLocation:
    """Localização planejada de um backup, sem criar ou copiar arquivos."""

    backup_id: str
    slot: SaveSlot
    created_at_utc: datetime
    destination: Path


_BACKUP_ID_PATTERN = re.compile(
    r"^save_(?P<slot>[1-9][0-9]{0,5})-"
    r"(?P<timestamp>[0-9]{8}T[0-9]{6}Z)-"
    r"(?P<suffix>[0-9a-f]{32})$"
)
_WINDOWS_INVALID_CHARACTERS = set('\\/:*?"<>|')
_MAX_SLOT_NUMBER = 999_999
_BACKUP_SUFFIX_LENGTH = 32


def create_backup_id(
    slot_number: int,
    *,
    created_at: datetime | None = None,
    suffix: str | None = None,
) -> str:
    """Cria um ID portátil contendo slot, instante UTC e sufixo hexadecimal."""
    _validate_slot_number(slot_number)
    timestamp = created_at if created_at is not None else datetime.now(UTC)
    _validate_utc_timestamp(timestamp)

    generated_suffix = secrets.token_hex(16) if suffix is None else suffix
    if not isinstance(generated_suffix, str) or not re.fullmatch(
        rf"[0-9a-f]{{{_BACKUP_SUFFIX_LENGTH}}}", generated_suffix
    ):
        raise BackupValidationError(
            BackupErrorCode.INVALID_SUFFIX,
            "O sufixo do backup deve ter 32 dígitos hexadecimais minúsculos.",
        )

    return f"save_{slot_number}-{timestamp:%Y%m%dT%H%M%SZ}-{generated_suffix}"


def resolve_backup_destination(
    slot: SaveSlot,
    active_save_root: Path | str,
    backup_root: Path | str,
    backup_id: str,
) -> BackupLocation:
    """Valida a origem e resolve um destino de backup sem modificar o disco."""
    _validate_slot_number(slot.number)
    parsed_id = _parse_backup_id(backup_id)
    if parsed_id[0] != slot.number:
        raise BackupValidationError(
            BackupErrorCode.INVALID_BACKUP_ID,
            "O identificador do backup não corresponde ao slot selecionado.",
        )

    source = _resolve_required_absolute_path(
        slot.path,
        BackupErrorCode.INCOHERENT_SOURCE,
        "A origem do backup não corresponde ao slot selecionado.",
    )
    game_data = _resolve_required_absolute_path(
        active_save_root,
        BackupErrorCode.INCOHERENT_SOURCE,
        "A pasta ativa de saves não é válida.",
    )
    if source != game_data / f"save_{slot.number}":
        raise BackupValidationError(
            BackupErrorCode.INCOHERENT_SOURCE,
            "A origem do backup não corresponde ao slot selecionado.",
        )

    root = _resolve_required_absolute_path(
        backup_root,
        BackupErrorCode.UNSAFE_BACKUP_ROOT,
        "A pasta de backups não é válida.",
    )
    if _is_within(root, game_data):
        raise BackupValidationError(
            BackupErrorCode.UNSAFE_BACKUP_ROOT,
            "A pasta de backups não pode ficar na pasta ativa de saves.",
        )
    if _is_within(source, root):
        raise BackupValidationError(
            BackupErrorCode.SOURCE_INSIDE_BACKUP_ROOT,
            "A origem do backup não pode ficar dentro da pasta de backups.",
        )

    destination = (root / backup_id).resolve(strict=False)
    if not _is_within(destination, root):
        raise BackupValidationError(
            BackupErrorCode.DESTINATION_OUTSIDE_BACKUP_ROOT,
            "O destino do backup não é seguro.",
        )

    return BackupLocation(
        backup_id=backup_id,
        slot=slot,
        created_at_utc=parsed_id[1],
        destination=destination,
    )


def _validate_slot_number(slot_number: int) -> None:
    if (
        isinstance(slot_number, bool)
        or not isinstance(slot_number, int)
        or not 1 <= slot_number <= _MAX_SLOT_NUMBER
    ):
        raise BackupValidationError(
            BackupErrorCode.INVALID_SLOT,
            "O número do slot deve ser um inteiro positivo de até seis dígitos.",
        )


def _validate_utc_timestamp(timestamp: object) -> None:
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is not UTC:
        raise BackupValidationError(
            BackupErrorCode.INVALID_TIMESTAMP,
            "A data do backup deve estar em UTC.",
        )


def _parse_backup_id(backup_id: str) -> tuple[int, datetime]:
    if not isinstance(backup_id, str) or any(char in backup_id for char in _WINDOWS_INVALID_CHARACTERS):
        raise BackupValidationError(BackupErrorCode.INVALID_BACKUP_ID, "Identificador de backup inválido.")
    match = _BACKUP_ID_PATTERN.fullmatch(backup_id)
    if match is None:
        raise BackupValidationError(BackupErrorCode.INVALID_BACKUP_ID, "Identificador de backup inválido.")
    try:
        timestamp = datetime.strptime(match["timestamp"], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise BackupValidationError(BackupErrorCode.INVALID_BACKUP_ID, "Identificador de backup inválido.") from error
    return int(match["slot"]), timestamp


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _resolve_required_absolute_path(
    value: Path | str,
    code: BackupErrorCode,
    public_message: str,
) -> Path:
    if isinstance(value, str) and not value.strip():
        raise BackupValidationError(code, public_message)

    try:
        path = Path(value)
    except TypeError as error:
        raise BackupValidationError(code, public_message) from error

    if not path.is_absolute():
        raise BackupValidationError(code, public_message)

    return path.resolve(strict=False)
