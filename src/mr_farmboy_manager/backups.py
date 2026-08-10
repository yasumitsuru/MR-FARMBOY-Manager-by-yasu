"""Contratos puros para identificação e localização segura de backups."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path, PurePosixPath

from .save_slots import SaveSlot


BACKUP_MANIFEST_FILENAME = "manifest.json"
BACKUP_PAYLOAD_DIRECTORY = "payload"
BACKUP_SCHEMA_VERSION = 1
MAX_BACKUP_MANIFEST_SIZE_BYTES = 32 * 1024 * 1024


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
    SOURCE_NOT_FOUND = "source_not_found"
    SOURCE_NOT_DIRECTORY = "source_not_directory"
    UNSAFE_SOURCE_ENTRY = "unsafe_source_entry"
    BACKUP_ROOT_UNAVAILABLE = "backup_root_unavailable"
    BACKUP_ALREADY_EXISTS = "backup_already_exists"
    COPY_FAILED = "copy_failed"
    SOURCE_CHANGED = "source_changed"
    VALIDATION_FAILED = "validation_failed"
    PUBLISH_FAILED = "publish_failed"
    CLEANUP_FAILED = "cleanup_failed"
    DISCOVERY_FAILED = "discovery_failed"
    RESTORE_NOT_CONFIRMED = "restore_not_confirmed"
    RESTORE_BACKUP_NOT_FOUND = "restore_backup_not_found"
    RESTORE_BACKUP_INVALID = "restore_backup_invalid"
    RESTORE_PREVENTIVE_BACKUP_FAILED = "restore_preventive_backup_failed"
    RESTORE_STAGING_FAILED = "restore_staging_failed"
    RESTORE_PUBLISH_FAILED = "restore_publish_failed"
    RESTORE_ROLLBACK_FAILED = "restore_rollback_failed"
    RESTORE_CLEANUP_PENDING = "restore_cleanup_pending"
    DELETE_NOT_CONFIRMED = "delete_not_confirmed"
    DELETE_BACKUP_NOT_FOUND = "delete_backup_not_found"
    DELETE_BACKUP_INVALID = "delete_backup_invalid"
    DELETE_FAILED = "delete_failed"
    DELETE_CLEANUP_PENDING = "delete_cleanup_pending"


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
    source: Path
    active_save_root: Path
    backup_root: Path
    destination: Path


@dataclass(frozen=True, slots=True)
class BackupFileRecord:
    """Metadados de integridade de um arquivo incluído no backup."""

    relative_path: str
    size_bytes: int
    modified_at_ns: int
    sha256: str


@dataclass(frozen=True, slots=True)
class BackupManifest:
    """Manifesto autocontido e sem caminhos pessoais."""

    backup_id: str
    slot_number: int
    created_at_utc: datetime
    files: tuple[BackupFileRecord, ...]

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_size_bytes(self) -> int:
        return sum(file.size_bytes for file in self.files)


@dataclass(frozen=True, slots=True)
class BackupRecord:
    """Resumo de um backup persistente criado com sucesso."""

    backup_id: str
    slot_number: int
    created_at_utc: datetime
    destination: Path
    file_count: int
    total_size_bytes: int


@dataclass(frozen=True, slots=True)
class BackupCreationResult:
    """Resultado sanitizado da criação de um backup."""

    backup: BackupRecord | None
    error_code: BackupErrorCode | None
    public_message: str

    @property
    def is_success(self) -> bool:
        return self.backup is not None and self.error_code is None


@dataclass(frozen=True, slots=True)
class BackupDiscoveryResult:
    """Resultado ordenado e sanitizado da descoberta de backups."""

    backups: tuple[BackupRecord, ...]
    invalid_entries: tuple[str, ...]
    error_code: BackupErrorCode | None
    public_message: str

    @property
    def is_success(self) -> bool:
        return self.error_code is None


@dataclass(frozen=True, slots=True)
class BackupRestoreResult:
    """Resultado sanitizado de uma restauração confirmada."""

    restored_backup: BackupRecord | None
    preventive_backup: BackupRecord | None
    error_code: BackupErrorCode | None
    public_message: str
    cleanup_pending: bool = False

    @property
    def is_success(self) -> bool:
        return self.restored_backup is not None and self.error_code in {
            None,
            BackupErrorCode.RESTORE_CLEANUP_PENDING,
        }


@dataclass(frozen=True, slots=True)
class BackupDeletionResult:
    """Resultado sanitizado da exclusão de um backup confirmado."""

    deleted_backup_id: str | None
    error_code: BackupErrorCode | None
    public_message: str
    cleanup_pending: bool = False

    @property
    def is_success(self) -> bool:
        return self.deleted_backup_id is not None and self.error_code in {
            None,
            BackupErrorCode.DELETE_CLEANUP_PENDING,
        }


PreventiveBackupCreator = Callable[[SaveSlot, Path | str, Path | str], BackupCreationResult]


@dataclass(frozen=True, slots=True)
class _SourceEntry:
    relative_path: str
    is_directory: bool
    device: int
    inode: int
    mode: int
    size_bytes: int
    modified_at_ns: int
    file_attributes: int


@dataclass(frozen=True, slots=True)
class _OpenedSource:
    descriptor: int
    initial_stat: os.stat_result
    windows_state: object | None = None


@dataclass(frozen=True, slots=True)
class _PathIdentity:
    path: Path
    device: int
    inode: int


class _BackupOperationFailure(Exception):
    def __init__(self, code: BackupErrorCode, public_message: str) -> None:
        self.code = code
        self.public_message = public_message
        super().__init__(public_message)


_BACKUP_ID_PATTERN = re.compile(
    r"^save_(?P<slot>[1-9][0-9]{0,5})-"
    r"(?P<timestamp>[0-9]{8}T[0-9]{6}Z)-"
    r"(?P<suffix>[0-9a-f]{32})$"
)
_WINDOWS_INVALID_CHARACTERS = set('\\/:*?"<>|')
_MAX_SLOT_NUMBER = 999_999
_BACKUP_SUFFIX_LENGTH = 32
_COPY_CHUNK_SIZE = 1024 * 1024
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


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
        source=source,
        active_save_root=game_data,
        backup_root=root,
        destination=destination,
    )


def create_backup(
    slot: SaveSlot,
    active_save_root: Path | str,
    backup_root: Path | str,
    *,
    created_at: datetime | None = None,
    suffix: str | None = None,
) -> BackupCreationResult:
    """Copia um slot para staging, valida e publica sem sobrescrever."""
    staging: Path | None = None
    result: BackupCreationResult

    try:
        backup_id = create_backup_id(
            slot.number,
            created_at=created_at,
            suffix=suffix,
        )
        _reject_existing_reparse_components(
            slot.path,
            BackupErrorCode.UNSAFE_SOURCE_ENTRY,
            "O slot selecionado contém um caminho não seguro.",
        )
        _reject_existing_reparse_components(
            active_save_root,
            BackupErrorCode.UNSAFE_SOURCE_ENTRY,
            "A pasta ativa de saves contém um caminho não seguro.",
        )
        _reject_existing_reparse_components(
            backup_root,
            BackupErrorCode.BACKUP_ROOT_UNAVAILABLE,
            "A pasta de backups contém um caminho não seguro.",
        )
        source_root_chain = _capture_existing_directory_chain(
            active_save_root,
            BackupErrorCode.UNSAFE_SOURCE_ENTRY,
            "A pasta ativa de saves contém um caminho não seguro.",
        )
        backup_initial_chain = _capture_existing_directory_chain(
            backup_root,
            BackupErrorCode.BACKUP_ROOT_UNAVAILABLE,
            "A pasta de backups contém um caminho não seguro.",
        )
        location = resolve_backup_destination(
            slot,
            active_save_root,
            backup_root,
            backup_id,
        )
        _assert_directory_chain(
            source_root_chain,
            BackupErrorCode.UNSAFE_SOURCE_ENTRY,
            "A pasta ativa de saves mudou durante a operação.",
        )
        _assert_directory_chain(
            backup_initial_chain,
            BackupErrorCode.BACKUP_ROOT_UNAVAILABLE,
            "A pasta de backups mudou durante a operação.",
        )
        source = location.source
        source_entries = _inventory_source_slot(source)
        root = location.backup_root
        _prepare_backup_root(root, backup_initial_chain)
        root_chain = _capture_directory_chain(root)

        _assert_directory_chain(root_chain)
        if os.path.lexists(location.destination):
            raise _BackupOperationFailure(
                BackupErrorCode.BACKUP_ALREADY_EXISTS,
                "Já existe um backup com esse identificador.",
            )

        staging = root / f".staging-{backup_id}-{secrets.token_hex(8)}"
        _assert_directory_chain(root_chain)
        staging.mkdir(exist_ok=False)
        staging_chain = _capture_directory_chain(staging)
        payload = staging / BACKUP_PAYLOAD_DIRECTORY
        _assert_directory_chain(staging_chain)
        payload.mkdir()
        payload_chain = _capture_directory_chain(payload)

        directories = [entry for entry in source_entries if entry.is_directory]
        files = [entry for entry in source_entries if not entry.is_directory]
        for entry in directories:
            directory = payload / Path(entry.relative_path)
            _assert_directory_chain(payload_chain)
            _assert_directory_chain(_capture_directory_chain(directory.parent))
            directory.mkdir(exist_ok=False)

        copied_files = tuple(
            _copy_regular_file(
                source / Path(entry.relative_path),
                payload / Path(entry.relative_path),
                entry,
                root_chain,
            )
            for entry in files
        )

        if _inventory_source_slot(source) != source_entries:
            raise _BackupOperationFailure(
                BackupErrorCode.SOURCE_CHANGED,
                "O save mudou durante a cópia. Feche o jogo e tente novamente.",
            )

        manifest = BackupManifest(
            backup_id=backup_id,
            slot_number=slot.number,
            created_at_utc=location.created_at_utc,
            files=copied_files,
        )
        _write_manifest(
            staging / BACKUP_MANIFEST_FILENAME,
            manifest,
            root_chain,
        )
        _validate_staged_backup(staging, manifest)

        _publish_staged_backup(
            staging,
            location.destination,
            root_chain,
        )
        staging = None
        record = BackupRecord(
            backup_id=manifest.backup_id,
            slot_number=manifest.slot_number,
            created_at_utc=manifest.created_at_utc,
            destination=location.destination,
            file_count=manifest.file_count,
            total_size_bytes=manifest.total_size_bytes,
        )
        result = BackupCreationResult(
            backup=record,
            error_code=None,
            public_message=f"Backup criado com sucesso: {record.backup_id}.",
        )
    except BackupValidationError as error:
        result = BackupCreationResult(None, error.code, error.public_message)
    except _BackupOperationFailure as error:
        result = BackupCreationResult(None, error.code, error.public_message)
    except OSError:
        result = BackupCreationResult(
            None,
            BackupErrorCode.COPY_FAILED,
            "Não foi possível copiar o save. Feche o jogo e tente novamente.",
        )

    cleanup_failed = False
    if staging is not None and os.path.lexists(staging):
        try:
            _assert_directory_chain(root_chain)
            current_staging = os.lstat(staging)
            if _has_reparse_attribute(current_staging):
                raise OSError
            shutil.rmtree(staging)
        except (OSError, UnboundLocalError, _BackupOperationFailure):
            cleanup_failed = True

    if cleanup_failed:
        return BackupCreationResult(
            None,
            BackupErrorCode.CLEANUP_FAILED,
            "O backup falhou e a pasta temporária não pôde ser removida.",
        )
    return result


def discover_backups(backup_root: Path | str) -> BackupDiscoveryResult:
    """Descobre manifestos válidos sem criar ou alterar a pasta de backups."""
    try:
        if isinstance(backup_root, str) and not backup_root.strip():
            raise ValueError
        root_input = Path(backup_root)
        if not root_input.is_absolute():
            raise ValueError
        _reject_existing_reparse_components(
            root_input,
            BackupErrorCode.DISCOVERY_FAILED,
            "A pasta de backups não é segura.",
        )
        if not os.path.lexists(root_input):
            return BackupDiscoveryResult(
                backups=(),
                invalid_entries=(),
                error_code=None,
                public_message="Nenhum backup encontrado.",
            )

        root = root_input.resolve(strict=True)
        root_state = os.lstat(root)
        if not stat.S_ISDIR(root_state.st_mode) or _has_reparse_attribute(root_state):
            raise ValueError

        records: list[BackupRecord] = []
        invalid_entries: list[str] = []
        with os.scandir(root) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        for entry in entries:
            if entry.name.startswith((".staging-", ".delete-trash-")):
                continue
            try:
                records.append(_read_backup_record(root, Path(entry.path)))
            except (BackupValidationError, _BackupOperationFailure, OSError, ValueError):
                invalid_entries.append(entry.name)

        records.sort(
            key=lambda record: (record.created_at_utc, record.backup_id),
            reverse=True,
        )
        invalid = tuple(sorted(invalid_entries))
        if records:
            message = f"{len(records)} backup(s) encontrado(s)."
        else:
            message = "Nenhum backup encontrado."
        if invalid:
            message += f" {len(invalid)} entrada(s) inválida(s) ignorada(s)."
        return BackupDiscoveryResult(tuple(records), invalid, None, message)
    except (BackupValidationError, _BackupOperationFailure, OSError, TypeError, ValueError):
        return BackupDiscoveryResult(
            backups=(),
            invalid_entries=(),
            error_code=BackupErrorCode.DISCOVERY_FAILED,
            public_message="Não foi possível listar os backups.",
        )


def restore_backup(
    slot: SaveSlot,
    active_save_root: Path | str,
    backup_root: Path | str,
    backup_id: str,
    *,
    confirmed: bool,
    preventive_backup_creator: PreventiveBackupCreator | None = None,
) -> BackupRestoreResult:
    """Restaura um backup validado por staging, troca e rollback."""
    if confirmed is not True:
        return BackupRestoreResult(
            None,
            None,
            BackupErrorCode.RESTORE_NOT_CONFIRMED,
            "A restauração não foi confirmada.",
        )

    staging: Path | None = None
    rollback: Path | None = None
    active_root_chain: tuple[_PathIdentity, ...] = ()
    staging_identity: os.stat_result | None = None
    staging_entries: tuple[_SourceEntry, ...] = ()
    preventive_record: BackupRecord | None = None
    preserve_partial_state = False

    try:
        parsed_slot, _parsed_timestamp = _parse_backup_id(backup_id)
        if parsed_slot != slot.number:
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_BACKUP_INVALID,
                "O backup selecionado não pertence ao slot de destino.",
            )

        _reject_existing_reparse_components(
            slot.path,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "O destino da restauração não é seguro.",
        )
        _reject_existing_reparse_components(
            active_save_root,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "A pasta ativa de saves não é segura.",
        )
        _reject_existing_reparse_components(
            backup_root,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "A pasta de backups não é segura.",
        )
        active_initial_chain = _capture_existing_directory_chain(
            active_save_root,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "A pasta ativa de saves não é segura.",
        )
        backup_initial_chain = _capture_existing_directory_chain(
            backup_root,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "A pasta de backups não é segura.",
        )
        location = resolve_backup_destination(
            slot,
            active_save_root,
            backup_root,
            backup_id,
        )
        _assert_directory_chain(
            active_initial_chain,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "A pasta ativa de saves mudou durante a restauração.",
        )
        _assert_directory_chain(
            backup_initial_chain,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "A pasta de backups mudou durante a restauração.",
        )

        active_root = location.active_save_root
        root = location.backup_root
        active_root_state = os.lstat(active_root)
        root_state = os.lstat(root)
        if (
            not stat.S_ISDIR(active_root_state.st_mode)
            or _has_reparse_attribute(active_root_state)
            or not stat.S_ISDIR(root_state.st_mode)
            or _has_reparse_attribute(root_state)
        ):
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_BACKUP_INVALID,
                "A origem ou o destino da restauração não é seguro.",
            )

        active_root_chain = _capture_directory_chain(active_root)
        backup_root_chain = _capture_directory_chain(root)
        active_slot_state = os.lstat(location.source)
        if (
            not stat.S_ISDIR(active_slot_state.st_mode)
            or _has_reparse_attribute(active_slot_state)
        ):
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_BACKUP_INVALID,
                "O destino da restauração não é seguro.",
            )
        active_entries = _inventory_source_slot(location.source)
        selected_record, selected_manifest = _load_validated_backup_for_restore(
            root,
            location.destination,
            slot.number,
        )

        creator = (
            preventive_backup_creator
            if preventive_backup_creator is not None
            else create_backup
        )
        try:
            preventive_result = creator(slot, active_root, root)
        except Exception as error:
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_PREVENTIVE_BACKUP_FAILED,
                "Não foi possível criar o backup preventivo.",
            ) from error
        if not preventive_result.is_success or preventive_result.backup is None:
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_PREVENTIVE_BACKUP_FAILED,
                "Não foi possível criar o backup preventivo.",
            )
        preventive_record = preventive_result.backup

        _assert_directory_chain(
            active_root_chain,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "A pasta ativa de saves mudou durante a restauração.",
        )
        _assert_directory_chain(
            backup_root_chain,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "A pasta de backups mudou durante a restauração.",
        )
        current_record, current_manifest = _load_validated_backup_for_restore(
            root,
            location.destination,
            slot.number,
        )
        if current_record != selected_record or current_manifest != selected_manifest:
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_BACKUP_INVALID,
                "O backup selecionado mudou durante a restauração.",
            )

        token = secrets.token_hex(16)
        staging_candidate = (
            active_root / f".restore-staging-save_{slot.number}-{token}"
        )
        rollback = active_root / f".restore-old-save_{slot.number}-{token}"
        if os.path.lexists(staging_candidate) or os.path.lexists(rollback):
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_STAGING_FAILED,
                "Não foi possível preparar a restauração.",
            )
        _assert_directory_chain(active_root_chain)
        staging_candidate.mkdir(exist_ok=False)
        staging = staging_candidate
        staging_identity = os.lstat(staging)
        _copy_backup_payload_to_staging(
            current_record.destination / BACKUP_PAYLOAD_DIRECTORY,
            staging,
            current_manifest,
        )
        staging_entries = _inventory_source_slot(staging)

        _assert_directory_chain(
            active_root_chain,
            BackupErrorCode.RESTORE_PUBLISH_FAILED,
            "A pasta ativa de saves mudou durante a restauração.",
        )
        if (
            not _same_stat_identity(os.lstat(location.source), active_slot_state)
            or _inventory_source_slot(location.source) != active_entries
        ):
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_PUBLISH_FAILED,
                "O save ativo mudou durante a restauração. Feche o jogo e tente novamente.",
            )
        final_record, final_manifest = _load_validated_backup_for_restore(
            root,
            location.destination,
            slot.number,
        )
        if final_record != current_record or final_manifest != current_manifest:
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_BACKUP_INVALID,
                "O backup selecionado mudou durante a restauração.",
            )
        if staging_identity is None:
            raise _BackupOperationFailure(
                BackupErrorCode.RESTORE_STAGING_FAILED,
                "Não foi possível preparar os arquivos da restauração.",
            )

        _publish_restored_slot(
            active_root,
            location.source,
            staging,
            rollback,
            current_manifest,
            active_root_chain,
            active_root_state,
            active_slot_state,
            active_entries,
            staging_identity,
            staging_entries,
        )
        staging = None

        try:
            _remove_restore_directory(
                rollback,
                active_root,
                active_root_chain,
                active_slot_state,
                expected_entries=active_entries,
            )
        except (OSError, _BackupOperationFailure):
            return BackupRestoreResult(
                current_record,
                preventive_record,
                BackupErrorCode.RESTORE_CLEANUP_PENDING,
                "O backup foi restaurado, mas uma limpeza temporária ficou pendente.",
                cleanup_pending=True,
            )
        rollback = None
        return BackupRestoreResult(
            current_record,
            preventive_record,
            None,
            f"Backup restaurado com sucesso: {current_record.backup_id}.",
        )
    except BackupValidationError as error:
        result = BackupRestoreResult(
            None,
            preventive_record,
            error.code,
            error.public_message,
        )
    except _BackupOperationFailure as error:
        preserve_partial_state = error.code is BackupErrorCode.RESTORE_ROLLBACK_FAILED
        result = BackupRestoreResult(
            None,
            preventive_record,
            error.code,
            error.public_message,
        )
    except (OSError, TypeError, ValueError):
        result = BackupRestoreResult(
            None,
            preventive_record,
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "Não foi possível validar a restauração.",
        )

    if (
        staging is not None
        and os.path.lexists(staging)
        and not preserve_partial_state
    ):
        try:
            active_root = staging.parent
            if staging_identity is None:
                raise OSError
            _remove_restore_directory(
                staging,
                active_root,
                active_root_chain,
                staging_identity,
                expected_entries=staging_entries,
            )
        except (OSError, _BackupOperationFailure):
            return BackupRestoreResult(
                None,
                preventive_record,
                BackupErrorCode.RESTORE_CLEANUP_PENDING,
                "A restauração foi cancelada, mas uma limpeza temporária ficou pendente.",
                cleanup_pending=True,
            )
    return result


def delete_backup(
    backup_root: Path | str,
    backup_id: str,
    *,
    confirmed: bool,
) -> BackupDeletionResult:
    """Exclui somente um backup íntegro, filho direto da raiz validada."""
    if confirmed is not True:
        return BackupDeletionResult(
            None,
            BackupErrorCode.DELETE_NOT_CONFIRMED,
            "A exclusão não foi confirmada.",
        )

    try:
        parsed_slot, _parsed_timestamp = _parse_backup_id(backup_id)
        _reject_existing_reparse_components(
            backup_root,
            BackupErrorCode.DELETE_BACKUP_INVALID,
            "A pasta de backups não é segura.",
        )
        root_input = _resolve_required_absolute_path(
            backup_root,
            BackupErrorCode.DELETE_BACKUP_INVALID,
            "A pasta de backups é inválida.",
        )
        if not os.path.lexists(root_input):
            raise _BackupOperationFailure(
                BackupErrorCode.DELETE_BACKUP_NOT_FOUND,
                "O backup selecionado não existe.",
            )
        initial_chain = _capture_existing_directory_chain(
            root_input,
            BackupErrorCode.DELETE_BACKUP_INVALID,
            "A pasta de backups não é segura.",
        )
        root = root_input.resolve(strict=True)
        root_state = os.lstat(root)
        if not stat.S_ISDIR(root_state.st_mode) or _has_reparse_attribute(root_state):
            raise _BackupOperationFailure(
                BackupErrorCode.DELETE_BACKUP_INVALID,
                "A pasta de backups não é segura.",
            )
        root_chain = _capture_directory_chain(root)
        _assert_directory_chain(
            initial_chain,
            BackupErrorCode.DELETE_BACKUP_INVALID,
            "A pasta de backups mudou durante a exclusão.",
        )

        target = root / backup_id
        if target.parent != root or not os.path.lexists(target):
            raise _BackupOperationFailure(
                BackupErrorCode.DELETE_BACKUP_NOT_FOUND,
                "O backup selecionado não existe.",
            )
        record, manifest, inventory = _load_validated_backup_for_delete(
            root,
            target,
            parsed_slot,
        )
        target_state = os.lstat(target)

        _assert_directory_chain(
            root_chain,
            BackupErrorCode.DELETE_FAILED,
            "A pasta de backups mudou durante a exclusão.",
        )
        current_record, current_manifest, current_inventory = (
            _load_validated_backup_for_delete(
                root,
                target,
                parsed_slot,
            )
        )
        if (
            current_record != record
            or current_manifest != manifest
            or current_inventory != inventory
            or not _same_stat_identity(os.lstat(target), target_state)
        ):
            raise _BackupOperationFailure(
                BackupErrorCode.DELETE_BACKUP_INVALID,
                "O backup selecionado mudou durante a exclusão.",
            )

        quarantine = root / f".delete-trash-{backup_id}-{secrets.token_hex(8)}"
        if os.path.lexists(quarantine):
            raise OSError
        _quarantine_backup_directory(
            target,
            quarantine,
            root,
            root_state,
            target_state,
        )

        try:
            quarantine_state = os.lstat(quarantine)
            if (
                os.path.lexists(target)
                or not _same_stat_identity(quarantine_state, target_state)
                or _inventory_source_slot(quarantine) != inventory
            ):
                raise OSError
            _remove_restore_directory(
                quarantine,
                root,
                root_chain,
                target_state,
                expected_entries=inventory,
            )
            if os.path.lexists(quarantine):
                raise OSError
        except (
            BackupValidationError,
            _BackupOperationFailure,
            OSError,
            TypeError,
            ValueError,
        ):
            return BackupDeletionResult(
                backup_id,
                BackupErrorCode.DELETE_CLEANUP_PENDING,
                "O backup foi excluído, mas uma limpeza temporária ficou pendente.",
                cleanup_pending=True,
            )
        return BackupDeletionResult(
            backup_id,
            None,
            f"Backup excluído com sucesso: {backup_id}.",
        )
    except BackupValidationError as error:
        return BackupDeletionResult(None, error.code, error.public_message)
    except _BackupOperationFailure as error:
        return BackupDeletionResult(None, error.code, error.public_message)
    except (OSError, TypeError, ValueError):
        return BackupDeletionResult(
            None,
            BackupErrorCode.DELETE_FAILED,
            "Não foi possível excluir o backup.",
        )


def _load_validated_backup_for_delete(
    root: Path,
    target: Path,
    expected_slot_number: int,
) -> tuple[BackupRecord, BackupManifest, tuple[_SourceEntry, ...]]:
    try:
        target_state = os.lstat(target)
        if (
            not stat.S_ISDIR(target_state.st_mode)
            or _has_reparse_attribute(target_state)
        ):
            raise ValueError
        with os.scandir(target) as iterator:
            top_level_names = {entry.name for entry in iterator}
        if top_level_names != {BACKUP_MANIFEST_FILENAME, BACKUP_PAYLOAD_DIRECTORY}:
            raise ValueError
        record, manifest = _read_backup_record_and_manifest(root, target)
        if record.slot_number != expected_slot_number:
            raise ValueError
        _validate_payload_against_manifest(
            target / BACKUP_PAYLOAD_DIRECTORY,
            manifest,
        )
        inventory = _inventory_source_slot(target)
        return record, manifest, inventory
    except (
        BackupValidationError,
        _BackupOperationFailure,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        raise _BackupOperationFailure(
            BackupErrorCode.DELETE_BACKUP_INVALID,
            "O backup selecionado está inválido ou incompleto.",
        ) from error


def _load_validated_backup_for_restore(
    root: Path,
    destination: Path,
    expected_slot_number: int,
) -> tuple[BackupRecord, BackupManifest]:
    if destination.parent != root or not os.path.lexists(destination):
        raise _BackupOperationFailure(
            BackupErrorCode.RESTORE_BACKUP_NOT_FOUND,
            "O backup selecionado não existe.",
        )
    try:
        record, manifest = _read_backup_record_and_manifest(root, destination)
        if record.slot_number != expected_slot_number:
            raise ValueError
        _validate_payload_against_manifest(
            destination / BACKUP_PAYLOAD_DIRECTORY,
            manifest,
        )
        return record, manifest
    except (
        BackupValidationError,
        _BackupOperationFailure,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        raise _BackupOperationFailure(
            BackupErrorCode.RESTORE_BACKUP_INVALID,
            "O backup selecionado está inválido ou incompleto.",
        ) from error


def _validate_payload_against_manifest(
    payload: Path,
    manifest: BackupManifest,
) -> None:
    entries = _inventory_source_slot(payload)
    files = {
        entry.relative_path: entry
        for entry in entries
        if not entry.is_directory
    }
    if set(files) != {record.relative_path for record in manifest.files}:
        raise ValueError
    for record in manifest.files:
        entry = files[record.relative_path]
        if (
            entry.size_bytes != record.size_bytes
            or entry.modified_at_ns != record.modified_at_ns
            or _sha256_source_entry(payload / Path(record.relative_path), entry)
            != record.sha256
        ):
            raise ValueError


def _sha256_source_entry(path: Path, expected: _SourceEntry) -> str:
    opened: _OpenedSource | None = None
    try:
        before = os.lstat(path)
        if _source_entry(expected.relative_path, before) != expected:
            raise ValueError
        opened = _open_source_descriptor(path, expected)
        digest = hashlib.sha256()
        while chunk := os.read(opened.descriptor, _COPY_CHUNK_SIZE):
            digest.update(chunk)
        if (
            _source_entry(expected.relative_path, os.lstat(path)) != expected
            or _source_entry(expected.relative_path, os.fstat(opened.descriptor))
            != expected
        ):
            raise ValueError
        _verify_windows_source_state(opened)
        return digest.hexdigest()
    finally:
        if opened is not None:
            os.close(opened.descriptor)


def _copy_backup_payload_to_staging(
    payload: Path,
    staging: Path,
    manifest: BackupManifest,
) -> None:
    try:
        entries = _inventory_source_slot(payload)
        staging_chain = _capture_directory_chain(staging)
        for entry in (item for item in entries if item.is_directory):
            destination = staging / Path(entry.relative_path)
            _assert_directory_chain(staging_chain)
            _assert_directory_chain(_capture_directory_chain(destination.parent))
            destination.mkdir(exist_ok=False)

        copied = tuple(
            _copy_regular_file(
                payload / Path(entry.relative_path),
                staging / Path(entry.relative_path),
                entry,
                staging_chain,
            )
            for entry in entries
            if not entry.is_directory
        )
        if copied != manifest.files or _inventory_source_slot(payload) != entries:
            raise ValueError
        _validate_payload_against_manifest(staging, manifest)
    except (OSError, TypeError, ValueError, _BackupOperationFailure) as error:
        raise _BackupOperationFailure(
            BackupErrorCode.RESTORE_STAGING_FAILED,
            "Não foi possível preparar os arquivos da restauração.",
        ) from error


def _publish_restored_slot(
    active_root: Path,
    active_slot: Path,
    staging: Path,
    rollback: Path,
    manifest: BackupManifest,
    active_root_chain: tuple[_PathIdentity, ...],
    expected_active_root_state: os.stat_result,
    expected_active_state: os.stat_result,
    expected_active_entries: tuple[_SourceEntry, ...],
    expected_staging_state: os.stat_result,
    expected_staging_entries: tuple[_SourceEntry, ...],
) -> None:
    old_moved = False
    restored_moved = False
    try:
        _assert_directory_chain(active_root_chain)
        current_active_state = os.lstat(active_slot)
        if (
            not _same_stat_identity(current_active_state, expected_active_state)
            or _inventory_source_slot(active_slot) != expected_active_entries
        ):
            raise OSError
        _rename_validated_directory(
            active_slot,
            rollback,
            active_root,
            expected_active_root_state,
            expected_active_state,
        )
        old_moved = True
        moved_state = os.lstat(rollback)
        if (
            not _same_stat_identity(moved_state, expected_active_state)
            or _inventory_source_slot(rollback) != expected_active_entries
        ):
            raise OSError
        _assert_directory_chain(active_root_chain)
        if os.path.lexists(active_slot):
            raise OSError
        if (
            not _same_stat_identity(os.lstat(staging), expected_staging_state)
            or _inventory_source_slot(staging) != expected_staging_entries
        ):
            raise OSError
        _rename_validated_directory(
            staging,
            active_slot,
            active_root,
            expected_active_root_state,
            expected_staging_state,
        )
        restored_moved = True
        _assert_directory_chain(active_root_chain)
        _validate_payload_against_manifest(active_slot, manifest)
        return
    except (OSError, TypeError, ValueError, _BackupOperationFailure) as error:
        if old_moved:
            try:
                _assert_directory_chain(active_root_chain)
                if restored_moved:
                    if os.path.lexists(staging):
                        raise OSError
                    _rename_validated_directory(
                        active_slot,
                        staging,
                        active_root,
                        expected_active_root_state,
                        expected_staging_state,
                    )
                if os.path.lexists(active_slot):
                    raise OSError
                _rename_validated_directory(
                    rollback,
                    active_slot,
                    active_root,
                    expected_active_root_state,
                    expected_active_state,
                )
            except (OSError, _BackupOperationFailure) as rollback_error:
                raise _BackupOperationFailure(
                    BackupErrorCode.RESTORE_ROLLBACK_FAILED,
                    "A restauração ficou em estado parcial; não mova os arquivos e feche o aplicativo.",
                ) from rollback_error
        raise _BackupOperationFailure(
            BackupErrorCode.RESTORE_PUBLISH_FAILED,
            "Não foi possível concluir a restauração; o save original foi preservado.",
        ) from error


def _remove_restore_directory(
    directory: Path,
    active_root: Path,
    active_root_chain: tuple[_PathIdentity, ...],
    expected_state: os.stat_result,
    *,
    expected_entries: tuple[_SourceEntry, ...],
) -> None:
    _assert_directory_chain(active_root_chain)
    if directory.parent != active_root:
        raise OSError
    state = os.lstat(directory)
    if (
        not stat.S_ISDIR(state.st_mode)
        or _has_reparse_attribute(state)
        or not _same_stat_identity(state, expected_state)
    ):
        raise OSError
    if os.name == "nt":
        _remove_restore_directory_windows(
            directory,
            expected_state,
            expected_entries=expected_entries,
        )
        return
    # POSIX does not offer a portable unlink-by-handle primitive.  A
    # quarantined backup therefore stays pending instead of risking that a
    # pathname swap makes cleanup delete an entry outside its inventory.
    raise OSError


def _rename_validated_directory(
    source: Path,
    destination: Path,
    root: Path,
    expected_root_state: os.stat_result,
    expected_source_state: os.stat_result,
) -> None:
    """Renomeia somente a identidade validada dentro da raiz ancorada."""
    if os.name != "nt":
        # Não há rename condicional por identidade em uma API POSIX portátil.
        # Falhar antes de mutar é mais seguro que voltar a um pathname solto.
        raise OSError
    _rename_validated_directory_windows(
        source,
        destination,
        root,
        expected_root_state,
        expected_source_state,
    )


def _quarantine_backup_directory(
    target: Path,
    quarantine: Path,
    root: Path,
    expected_root_state: os.stat_result,
    expected_target_state: os.stat_result,
) -> None:
    """Move a identidade validada para quarentena antes da remoção física."""
    _rename_validated_directory(
        target,
        quarantine,
        root,
        expected_root_state,
        expected_target_state,
    )


def _quarantine_backup_directory_windows(
    target: Path,
    quarantine: Path,
    root: Path,
    expected_root_state: os.stat_result,
    expected_target_state: os.stat_result,
) -> None:
    """Compatibilidade interna para a primitive Win32 de quarentena."""
    _rename_validated_directory_windows(
        target,
        quarantine,
        root,
        expected_root_state,
        expected_target_state,
    )


def _rename_validated_directory_windows(
    target: Path,
    quarantine: Path,
    root: Path,
    expected_root_state: os.stat_result,
    expected_target_state: os.stat_result,
) -> None:
    """Renomeia pelo handle Win32 da própria identidade validada."""
    import ctypes
    import ntpath
    from ctypes import wintypes

    from . import save_details as secure_reader

    class _FileRenameInfo(ctypes.Structure):
        _fields_ = [
            ("replace_or_flags", wintypes.DWORD),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * 1),
        ]

    class _IoStatusBlock(ctypes.Structure):
        _fields_ = [
            ("status_or_pointer", ctypes.c_void_p),
            ("information", ctypes.c_size_t),
        ]

    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    nt_set_information = ntdll.NtSetInformationFile
    nt_set_information.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_IoStatusBlock),
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.c_int,
    ]
    nt_set_information.restype = wintypes.LONG
    delete_access = 0x00010000
    file_rename_information_class = 10
    root_handle: int | None = None
    target_handle: int | None = None
    renamed = False

    try:
        if target.parent != root or quarantine.parent != root:
            raise OSError
        root_handle = secure_reader._open_win32_handle(
            root,
            secure_reader._FILE_READ_ATTRIBUTES,
            secure_reader._FILE_FLAG_BACKUP_SEMANTICS
            | secure_reader._FILE_FLAG_OPEN_REPARSE_POINT,
        )
        root_information = secure_reader._get_win32_file_information(root_handle)
        root_final_path = secure_reader._normalize_win32_final_path(
            secure_reader._get_win32_final_path(root_handle)
        )
        expected_root_path = ntpath.normpath(str(root)).rstrip("\\/").casefold()
        if (
            root_information.file_index != expected_root_state.st_ino
            or root_final_path != expected_root_path
            or root_information.attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or not root_information.attributes
            & secure_reader._FILE_ATTRIBUTE_DIRECTORY
        ):
            raise OSError

        target_handle = secure_reader._open_win32_handle(
            target,
            delete_access | secure_reader._FILE_READ_ATTRIBUTES,
            secure_reader._FILE_FLAG_BACKUP_SEMANTICS
            | secure_reader._FILE_FLAG_OPEN_REPARSE_POINT,
        )
        target_information = secure_reader._get_win32_file_information(target_handle)
        target_final_path = secure_reader._normalize_win32_final_path(
            secure_reader._get_win32_final_path(target_handle)
        )
        expected_target_path = ntpath.normpath(str(target)).rstrip("\\/").casefold()
        if (
            target_information.file_index != expected_target_state.st_ino
            or target_final_path != expected_target_path
            or ntpath.dirname(target_final_path) != root_final_path
            or target_information.attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or not target_information.attributes
            & secure_reader._FILE_ATTRIBUTE_DIRECTORY
        ):
            raise OSError

        encoded_name = quarantine.name.encode("utf-16-le")
        file_name_offset = _FileRenameInfo.file_name.offset
        buffer_size = max(
            ctypes.sizeof(_FileRenameInfo),
            file_name_offset + len(encoded_name) + ctypes.sizeof(wintypes.WCHAR),
        )
        buffer = ctypes.create_string_buffer(buffer_size)
        information = ctypes.cast(
            buffer,
            ctypes.POINTER(_FileRenameInfo),
        ).contents
        information.replace_or_flags = 0
        information.root_directory = root_handle
        information.file_name_length = len(encoded_name)
        ctypes.memmove(
            ctypes.addressof(buffer) + file_name_offset,
            encoded_name,
            len(encoded_name),
        )
        io_status = _IoStatusBlock()
        status = nt_set_information(
            target_handle,
            ctypes.byref(io_status),
            ctypes.byref(buffer),
            buffer_size,
            file_rename_information_class,
        )
        if status < 0:
            raise OSError
        renamed = True
    finally:
        active_error = sys.exception()
        close_error: OSError | None = None
        for handle in (target_handle, root_handle):
            if handle is None:
                continue
            try:
                secure_reader._close_win32_handle(handle)
            except OSError as error:
                if close_error is None:
                    close_error = error
        if close_error is not None and active_error is None and not renamed:
            raise close_error


def _remove_restore_directory_windows(
    directory: Path,
    expected_state: os.stat_result,
    *,
    expected_entries: tuple[_SourceEntry, ...],
) -> None:
    """Remove a árvore exata por handles Win32 sem seguir substituições."""
    import ctypes
    import ntpath
    from ctypes import wintypes

    from . import save_details as secure_reader

    class _FileDispositionInfo(ctypes.Structure):
        _fields_ = [("delete_file", ctypes.c_ubyte)]

    set_file_information = secure_reader._KERNEL32.SetFileInformationByHandle
    set_file_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    set_file_information.restype = wintypes.BOOL
    delete_access = 0x00010000
    file_disposition_info_class = 4

    expected_children: dict[str, list[_SourceEntry]] = {}
    for entry in expected_entries:
        parent = PurePosixPath(entry.relative_path).parent.as_posix()
        expected_children.setdefault("" if parent == "." else parent, []).append(
            entry
        )
    for children in expected_children.values():
        children.sort(key=lambda entry: entry.relative_path)

    def remove_node(
        path: Path,
        expected: os.stat_result | _SourceEntry,
        relative_path: str = "",
    ) -> None:
        is_directory = (
            expected.is_directory
            if isinstance(expected, _SourceEntry)
            else stat.S_ISDIR(expected.st_mode)
        )
        expected_inode = (
            expected.inode if isinstance(expected, _SourceEntry) else expected.st_ino
        )
        flags = secure_reader._FILE_FLAG_OPEN_REPARSE_POINT
        if is_directory:
            flags |= secure_reader._FILE_FLAG_BACKUP_SEMANTICS

        handle: int | None = None
        try:
            handle = secure_reader._open_win32_handle(
                path,
                delete_access | secure_reader._FILE_READ_ATTRIBUTES,
                flags,
            )
            information = secure_reader._get_win32_file_information(handle)
            final_path = secure_reader._normalize_win32_final_path(
                secure_reader._get_win32_final_path(handle)
            )
            expected_path = ntpath.normpath(str(path)).rstrip("\\/").casefold()
            handle_is_directory = bool(
                information.attributes & secure_reader._FILE_ATTRIBUTE_DIRECTORY
            )
            if (
                information.file_index != expected_inode
                or final_path != expected_path
                or information.attributes & _FILE_ATTRIBUTE_REPARSE_POINT
                or handle_is_directory != is_directory
            ):
                raise OSError

            if is_directory:
                with os.scandir(path) as iterator:
                    children = sorted(iterator, key=lambda entry: entry.name)
                expected_for_directory = expected_children.get(relative_path, [])
                expected_names = {
                    PurePosixPath(entry.relative_path).name
                    for entry in expected_for_directory
                }
                if {child.name for child in children} != expected_names:
                    raise OSError
                children_to_remove = []
                for child_expected in expected_for_directory:
                    child_name = PurePosixPath(child_expected.relative_path).name
                    child_path = path / child_name
                    child_state = os.lstat(child_path)
                    if (
                        _has_reparse_attribute(child_state)
                        or _source_entry(
                            child_expected.relative_path,
                            child_state,
                        )
                        != child_expected
                    ):
                        raise OSError
                    children_to_remove.append(
                        (
                            child_path,
                            child_expected,
                            child_expected.relative_path,
                        )
                    )

                for child_path, child_expected, child_relative_path in children_to_remove:
                    remove_node(child_path, child_expected, child_relative_path)
                with os.scandir(path) as iterator:
                    if next(iterator, None) is not None:
                        raise OSError

            disposition = _FileDispositionInfo(1)
            if not set_file_information(
                handle,
                file_disposition_info_class,
                ctypes.byref(disposition),
                ctypes.sizeof(disposition),
            ):
                raise OSError
        finally:
            if handle is not None:
                secure_reader._close_win32_handle(handle)

    remove_node(directory, expected_state)


def _read_backup_record(root: Path, directory: Path) -> BackupRecord:
    record, _manifest = _read_backup_record_and_manifest(root, directory)
    return record


def _read_backup_record_and_manifest(
    root: Path,
    directory: Path,
) -> tuple[BackupRecord, BackupManifest]:
    directory_state = os.lstat(directory)
    if (
        not stat.S_ISDIR(directory_state.st_mode)
        or _has_reparse_attribute(directory_state)
        or directory.parent != root
    ):
        raise ValueError

    parsed_slot, parsed_timestamp = _parse_backup_id(directory.name)
    manifest_path = directory / BACKUP_MANIFEST_FILENAME
    payload_path = directory / BACKUP_PAYLOAD_DIRECTORY
    manifest_state = os.lstat(manifest_path)
    payload_state = os.lstat(payload_path)
    if (
        not stat.S_ISREG(manifest_state.st_mode)
        or _has_reparse_attribute(manifest_state)
        or manifest_state.st_size > MAX_BACKUP_MANIFEST_SIZE_BYTES
        or not stat.S_ISDIR(payload_state.st_mode)
        or _has_reparse_attribute(payload_state)
    ):
        raise ValueError

    raw = _read_manifest_bytes(manifest_path, manifest_state)
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "backup_id",
        "slot_number",
        "created_at_utc",
        "file_count",
        "total_size_bytes",
        "files",
    }:
        raise ValueError
    if (
        not _is_plain_int(document["schema_version"])
        or document["schema_version"] != BACKUP_SCHEMA_VERSION
    ):
        raise ValueError
    if document["backup_id"] != directory.name:
        raise ValueError
    if not _is_plain_int(document["slot_number"]):
        raise ValueError
    if document["slot_number"] != parsed_slot:
        raise ValueError

    created_at = datetime.strptime(
        _required_string(document["created_at_utc"]),
        "%Y-%m-%dT%H:%M:%SZ",
    ).replace(tzinfo=UTC)
    if created_at != parsed_timestamp:
        raise ValueError

    files_value = document["files"]
    if not isinstance(files_value, list):
        raise ValueError
    files = tuple(_parse_backup_file_record(value) for value in files_value)
    relative_paths = [file.relative_path for file in files]
    if len(relative_paths) != len(set(relative_paths)):
        raise ValueError
    if relative_paths != sorted(relative_paths):
        raise ValueError
    if (
        not _is_plain_int(document["file_count"])
        or document["file_count"] != len(files)
        or not _is_plain_int(document["total_size_bytes"])
        or document["total_size_bytes"] != sum(file.size_bytes for file in files)
    ):
        raise ValueError

    payload_entries = _inventory_source_slot(payload_path)
    payload_files = {
        entry.relative_path: entry
        for entry in payload_entries
        if not entry.is_directory
    }
    if set(payload_files) != set(relative_paths):
        raise ValueError
    if any(
        payload_files[file.relative_path].size_bytes != file.size_bytes
        for file in files
    ):
        raise ValueError

    manifest = BackupManifest(
        backup_id=directory.name,
        slot_number=parsed_slot,
        created_at_utc=created_at,
        files=files,
    )
    record = BackupRecord(
        backup_id=directory.name,
        slot_number=parsed_slot,
        created_at_utc=created_at,
        destination=directory,
        file_count=len(files),
        total_size_bytes=sum(file.size_bytes for file in files),
    )
    return record, manifest


def _read_manifest_bytes(
    manifest_path: Path,
    manifest_state: os.stat_result,
) -> bytes:
    expected = _source_entry(BACKUP_MANIFEST_FILENAME, manifest_state)
    opened: _OpenedSource | None = None
    try:
        opened = _open_source_descriptor(manifest_path, expected)
        remaining = MAX_BACKUP_MANIFEST_SIZE_BYTES + 1
        chunks: list[bytes] = []
        total = 0
        while remaining > 0:
            block = os.read(
                opened.descriptor,
                min(_COPY_CHUNK_SIZE, remaining),
            )
            if not block:
                break
            chunks.append(block)
            total += len(block)
            remaining -= len(block)
        if total > MAX_BACKUP_MANIFEST_SIZE_BYTES:
            raise ValueError
        if _source_entry(
            BACKUP_MANIFEST_FILENAME,
            os.fstat(opened.descriptor),
        ) != expected:
            raise ValueError
        _verify_windows_source_state(opened)
        return b"".join(chunks)
    finally:
        if opened is not None:
            try:
                os.close(opened.descriptor)
            except OSError:
                if sys.exception() is None:
                    raise ValueError from None


def _parse_backup_file_record(value: object) -> BackupFileRecord:
    if not isinstance(value, dict) or set(value) != {
        "relative_path",
        "size_bytes",
        "modified_at_ns",
        "sha256",
    }:
        raise ValueError
    relative_path = _required_string(value["relative_path"])
    parsed_path = PurePosixPath(relative_path)
    if (
        "\\" in relative_path
        or parsed_path.is_absolute()
        or not parsed_path.parts
        or any(part in {"", ".", ".."} for part in parsed_path.parts)
        or parsed_path.as_posix() != relative_path
    ):
        raise ValueError
    size_bytes = value["size_bytes"]
    modified_at_ns = value["modified_at_ns"]
    sha256 = value["sha256"]
    if (
        not _is_plain_int(size_bytes)
        or size_bytes < 0
        or not _is_plain_int(modified_at_ns)
        or modified_at_ns < 0
        or not isinstance(sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
    ):
        raise ValueError
    return BackupFileRecord(relative_path, size_bytes, modified_at_ns, sha256)


def _required_string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError
    return value


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _inventory_source_slot(source: Path) -> tuple[_SourceEntry, ...]:
    try:
        root_state = os.lstat(source)
    except FileNotFoundError as error:
        raise _BackupOperationFailure(
            BackupErrorCode.SOURCE_NOT_FOUND,
            "O slot selecionado não existe.",
        ) from error
    except OSError as error:
        raise _BackupOperationFailure(
            BackupErrorCode.COPY_FAILED,
            "Não foi possível acessar o slot selecionado.",
        ) from error

    if not stat.S_ISDIR(root_state.st_mode):
        raise _BackupOperationFailure(
            BackupErrorCode.SOURCE_NOT_DIRECTORY,
            "O slot selecionado não é uma pasta.",
        )
    if _has_reparse_attribute(root_state):
        raise _BackupOperationFailure(
            BackupErrorCode.UNSAFE_SOURCE_ENTRY,
            "O slot selecionado contém um caminho não seguro.",
        )

    entries: list[_SourceEntry] = []
    pending = [source]
    while pending:
        directory = pending.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            raise _BackupOperationFailure(
                BackupErrorCode.COPY_FAILED,
                "Não foi possível ler todos os arquivos do slot.",
            ) from error

        for child in children:
            child_path = Path(child.path)
            try:
                # ``DirEntry.stat`` reports zeroed inode/device values on some
                # Windows filesystems.  ``lstat`` keeps the comparison stable
                # with the checks performed immediately before and after copy.
                child_state = os.lstat(child_path)
            except OSError as error:
                raise _BackupOperationFailure(
                    BackupErrorCode.COPY_FAILED,
                    "Não foi possível ler todos os arquivos do slot.",
                ) from error

            if _has_reparse_attribute(child_state):
                raise _BackupOperationFailure(
                    BackupErrorCode.UNSAFE_SOURCE_ENTRY,
                    "O slot selecionado contém um caminho não seguro.",
                )

            relative_path = child_path.relative_to(source).as_posix()
            entry = _source_entry(relative_path, child_state)
            if entry.is_directory:
                pending.append(child_path)
            elif not stat.S_ISREG(entry.mode):
                raise _BackupOperationFailure(
                    BackupErrorCode.UNSAFE_SOURCE_ENTRY,
                    "O slot selecionado contém um tipo de arquivo não suportado.",
                )
            entries.append(entry)

    entries.sort(key=lambda entry: entry.relative_path)
    return tuple(entries)


def _source_entry(relative_path: str, state: os.stat_result) -> _SourceEntry:
    return _SourceEntry(
        relative_path=relative_path,
        is_directory=stat.S_ISDIR(state.st_mode),
        device=state.st_dev,
        inode=state.st_ino,
        mode=state.st_mode,
        size_bytes=state.st_size,
        modified_at_ns=state.st_mtime_ns,
        file_attributes=getattr(state, "st_file_attributes", 0),
    )


def _has_reparse_attribute(state: os.stat_result) -> bool:
    return stat.S_ISLNK(state.st_mode) or bool(
        getattr(state, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _reject_existing_reparse_components(
    value: Path | str,
    code: BackupErrorCode,
    public_message: str,
) -> None:
    try:
        path = Path(value)
    except TypeError:
        return
    if not path.is_absolute():
        return

    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if not os.path.lexists(current):
            break
        try:
            state = os.lstat(current)
        except OSError as error:
            raise _BackupOperationFailure(code, public_message) from error
        if _has_reparse_attribute(state):
            raise _BackupOperationFailure(code, public_message)


def _prepare_backup_root(
    root: Path,
    initial_chain: tuple[_PathIdentity, ...],
) -> None:
    if os.name != "nt":
        _prepare_backup_root_posix(root, initial_chain)
        return

    expected = {identity.path: identity for identity in initial_chain}
    try:
        current = Path(root.anchor)
        for component in root.parts[1:]:
            current /= component
            if not os.path.lexists(current):
                _assert_directory_chain(initial_chain)
                current.mkdir()
            state = os.lstat(current)
            if not stat.S_ISDIR(state.st_mode) or _has_reparse_attribute(state):
                raise OSError
            expected_identity = expected.get(current)
            if expected_identity is not None and (
                state.st_dev,
                state.st_ino,
            ) != (expected_identity.device, expected_identity.inode):
                raise OSError
        root_state = os.lstat(root)
    except OSError as error:
        raise _BackupOperationFailure(
            BackupErrorCode.BACKUP_ROOT_UNAVAILABLE,
            "A pasta de backups não está disponível.",
        ) from error

    if not stat.S_ISDIR(root_state.st_mode) or _has_reparse_attribute(root_state):
        raise _BackupOperationFailure(
            BackupErrorCode.BACKUP_ROOT_UNAVAILABLE,
            "A pasta de backups não é segura.",
        )


def _prepare_backup_root_posix(
    root: Path,
    initial_chain: tuple[_PathIdentity, ...],
) -> None:
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    current_directory: int | None = None
    current_path = Path(root.anchor)
    expected = {identity.path: identity for identity in initial_chain}
    try:
        current_directory = os.open(root.anchor, directory_flags)
        for component in root.parts[1:]:
            current_path /= component
            try:
                next_directory = os.open(
                    component,
                    directory_flags,
                    dir_fd=current_directory,
                )
            except FileNotFoundError:
                _assert_directory_chain(initial_chain)
                os.mkdir(component, dir_fd=current_directory)
                next_directory = os.open(
                    component,
                    directory_flags,
                    dir_fd=current_directory,
                )
            opened_state = os.fstat(next_directory)
            expected_identity = expected.get(current_path)
            if (
                not stat.S_ISDIR(opened_state.st_mode)
                or _has_reparse_attribute(opened_state)
                or (
                    expected_identity is not None
                    and (opened_state.st_dev, opened_state.st_ino)
                    != (expected_identity.device, expected_identity.inode)
                )
            ):
                os.close(next_directory)
                raise OSError
            os.close(current_directory)
            current_directory = next_directory
    except (OSError, TypeError, ValueError) as error:
        raise _BackupOperationFailure(
            BackupErrorCode.BACKUP_ROOT_UNAVAILABLE,
            "A pasta de backups não está disponível.",
        ) from error
    finally:
        if current_directory is not None:
            try:
                os.close(current_directory)
            except OSError:
                pass


def _capture_directory_chain(path: Path) -> tuple[_PathIdentity, ...]:
    identities: list[_PathIdentity] = []
    current = Path(path.anchor)
    try:
        for component in path.parts[1:]:
            current /= component
            state = os.lstat(current)
            if not stat.S_ISDIR(state.st_mode) or _has_reparse_attribute(state):
                raise OSError
            identities.append(_PathIdentity(current, state.st_dev, state.st_ino))
    except OSError as error:
        raise _BackupOperationFailure(
            BackupErrorCode.BACKUP_ROOT_UNAVAILABLE,
            "A cadeia de diretórios do backup não é segura.",
        ) from error
    return tuple(identities)


def _capture_existing_directory_chain(
    value: Path | str,
    code: BackupErrorCode,
    public_message: str,
) -> tuple[_PathIdentity, ...]:
    try:
        path = Path(value)
    except TypeError:
        return ()
    if not path.is_absolute():
        return ()

    identities: list[_PathIdentity] = []
    current = Path(path.anchor)
    try:
        for component in path.parts[1:]:
            current /= component
            if not os.path.lexists(current):
                break
            state = os.lstat(current)
            if not stat.S_ISDIR(state.st_mode) or _has_reparse_attribute(state):
                raise OSError
            identities.append(_PathIdentity(current, state.st_dev, state.st_ino))
    except OSError as error:
        raise _BackupOperationFailure(code, public_message) from error
    return tuple(identities)


def _assert_directory_chain(
    chain: tuple[_PathIdentity, ...],
    code: BackupErrorCode = BackupErrorCode.BACKUP_ROOT_UNAVAILABLE,
    public_message: str = "A cadeia de diretórios do backup mudou durante a operação.",
) -> None:
    try:
        for identity in chain:
            current = os.lstat(identity.path)
            if (
                not stat.S_ISDIR(current.st_mode)
                or _has_reparse_attribute(current)
                or (current.st_dev, current.st_ino)
                != (identity.device, identity.inode)
            ):
                raise OSError
    except OSError as error:
        raise _BackupOperationFailure(
            code,
            public_message,
        ) from error


def _copy_regular_file(
    source: Path,
    destination: Path,
    expected_state: _SourceEntry,
    backup_root_chain: tuple[_PathIdentity, ...],
) -> BackupFileRecord:
    opened: _OpenedSource | None = None
    try:
        before = os.lstat(source)
        if _source_entry(expected_state.relative_path, before) != expected_state:
            raise _BackupOperationFailure(
                BackupErrorCode.SOURCE_CHANGED,
                "O save mudou durante a cópia. Feche o jogo e tente novamente.",
            )
        opened = _open_source_descriptor(source, expected_state)

        digest = hashlib.sha256()
        copied_size = 0
        _assert_directory_chain(backup_root_chain)
        _assert_directory_chain(_capture_directory_chain(destination.parent))
        with destination.open("xb") as destination_file:
            while chunk := os.read(opened.descriptor, _COPY_CHUNK_SIZE):
                destination_file.write(chunk)
                digest.update(chunk)
                copied_size += len(chunk)
            destination_file.flush()
            os.fsync(destination_file.fileno())

        after = os.lstat(source)
        if (
            _source_entry(expected_state.relative_path, after) != expected_state
            or _source_entry(
                expected_state.relative_path,
                os.fstat(opened.descriptor),
            )
            != expected_state
            or copied_size != expected_state.size_bytes
        ):
            raise _BackupOperationFailure(
                BackupErrorCode.SOURCE_CHANGED,
                "O save mudou durante a cópia. Feche o jogo e tente novamente.",
            )
        _verify_windows_source_state(opened)
        os.utime(
            destination,
            ns=(expected_state.modified_at_ns, expected_state.modified_at_ns),
        )
    except _BackupOperationFailure:
        raise
    except OSError as error:
        raise _BackupOperationFailure(
            BackupErrorCode.COPY_FAILED,
            "Não foi possível copiar todos os arquivos do save.",
        ) from error
    finally:
        if opened is not None:
            try:
                os.close(opened.descriptor)
            except OSError:
                if sys.exception() is None:
                    raise _BackupOperationFailure(
                        BackupErrorCode.COPY_FAILED,
                        "Não foi possível concluir a leitura segura do save.",
                    ) from None

    return BackupFileRecord(
        relative_path=expected_state.relative_path,
        size_bytes=copied_size,
        modified_at_ns=expected_state.modified_at_ns,
        sha256=digest.hexdigest(),
    )


def _open_source_descriptor(
    source: Path,
    expected_state: _SourceEntry,
) -> _OpenedSource:
    if os.name == "nt":
        return _open_source_descriptor_windows(source, expected_state)
    return _open_source_descriptor_posix(source, expected_state)


def _open_source_descriptor_posix(
    source: Path,
    expected_state: _SourceEntry,
) -> _OpenedSource:
    parts = Path(expected_state.relative_path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise _BackupOperationFailure(
            BackupErrorCode.SOURCE_CHANGED,
            "O save mudou durante a cópia. Feche o jogo e tente novamente.",
        )

    source_root = source
    for _ in parts:
        source_root = source_root.parent

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    current_directory: int | None = None
    descriptor: int | None = None
    try:
        current_directory = os.open(source_root.anchor, directory_flags)
        for component in (*source_root.parts[1:], *parts[:-1]):
            next_directory = os.open(
                component,
                directory_flags,
                dir_fd=current_directory,
            )
            os.close(current_directory)
            current_directory = next_directory
        descriptor = os.open(
            parts[-1],
            file_flags,
            dir_fd=current_directory,
        )
        opened_stat = os.fstat(descriptor)
        if _source_entry(expected_state.relative_path, opened_stat) != expected_state:
            raise OSError
        opened = _OpenedSource(descriptor, opened_stat)
        descriptor = None
        return opened
    except (OSError, TypeError, ValueError) as error:
        raise _BackupOperationFailure(
            BackupErrorCode.SOURCE_CHANGED,
            "O save mudou durante a cópia. Feche o jogo e tente novamente.",
        ) from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if current_directory is not None:
            try:
                os.close(current_directory)
            except OSError:
                pass


def _open_source_descriptor_windows(
    source: Path,
    expected_state: _SourceEntry,
) -> _OpenedSource:
    import msvcrt
    import ntpath

    from . import save_details as secure_reader

    parent_handle: int | None = None
    file_handle: int | None = None
    descriptor: int | None = None
    try:
        parent_handle = secure_reader._open_win32_handle(
            source.parent,
            secure_reader._FILE_READ_ATTRIBUTES,
            secure_reader._FILE_FLAG_BACKUP_SEMANTICS
            | secure_reader._FILE_FLAG_OPEN_REPARSE_POINT,
        )
        parent_info = secure_reader._get_win32_file_information(parent_handle)
        parent_final = secure_reader._normalize_win32_final_path(
            secure_reader._get_win32_final_path(parent_handle)
        )
        expected_parent = ntpath.normpath(str(source.parent)).rstrip("\\/").casefold()
        if (
            parent_info.attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or not parent_info.attributes & secure_reader._FILE_ATTRIBUTE_DIRECTORY
            or parent_final != expected_parent
        ):
            raise OSError

        file_handle = secure_reader._open_win32_handle(
            source,
            secure_reader._GENERIC_READ,
            secure_reader._FILE_FLAG_OPEN_REPARSE_POINT
            | secure_reader._FILE_FLAG_SEQUENTIAL_SCAN,
        )
        file_info = secure_reader._get_win32_file_information(file_handle)
        file_final = secure_reader._normalize_win32_final_path(
            secure_reader._get_win32_final_path(file_handle)
        )
        expected_file = ntpath.normpath(str(source)).rstrip("\\/").casefold()
        if (
            file_info.attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or file_info.attributes & secure_reader._FILE_ATTRIBUTE_DIRECTORY
            or file_final != expected_file
        ):
            raise OSError

        descriptor = msvcrt.open_osfhandle(
            file_handle,
            os.O_RDONLY | getattr(os, "O_BINARY", 0),
        )
        file_handle = None
        opened_stat = os.fstat(descriptor)
        if _source_entry(expected_state.relative_path, opened_stat) != expected_state:
            raise OSError
        opened = _OpenedSource(descriptor, opened_stat, file_info)
        descriptor = None
        return opened
    except (OSError, OverflowError, ValueError) as error:
        raise _BackupOperationFailure(
            BackupErrorCode.SOURCE_CHANGED,
            "O save mudou durante a cópia. Feche o jogo e tente novamente.",
        ) from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if file_handle is not None:
            try:
                secure_reader._close_win32_handle(file_handle)
            except OSError:
                pass
        if parent_handle is not None:
            try:
                secure_reader._close_win32_handle(parent_handle)
            except OSError:
                pass


def _verify_windows_source_state(opened: _OpenedSource) -> None:
    if opened.windows_state is None:
        return

    import msvcrt

    from . import save_details as secure_reader

    final_state = secure_reader._get_win32_file_information(
        msvcrt.get_osfhandle(opened.descriptor)
    )
    if not secure_reader._same_win32_file_state(
        opened.windows_state,
        final_state,
    ):
        raise _BackupOperationFailure(
            BackupErrorCode.SOURCE_CHANGED,
            "O save mudou durante a cópia. Feche o jogo e tente novamente.",
        )


def _publish_staged_backup(
    staging: Path,
    destination: Path,
    backup_root_chain: tuple[_PathIdentity, ...],
) -> None:
    reserved_state: os.stat_result | None = None
    try:
        _assert_directory_chain(backup_root_chain)
        destination.mkdir(exist_ok=False)
        reserved_state = os.lstat(destination)
    except FileExistsError as error:
        raise _BackupOperationFailure(
            BackupErrorCode.BACKUP_ALREADY_EXISTS,
            "Já existe um backup com esse identificador.",
        ) from error
    except OSError as error:
        raise _BackupOperationFailure(
            BackupErrorCode.PUBLISH_FAILED,
            "Não foi possível concluir o backup.",
        ) from error

    try:
        _assert_directory_chain(backup_root_chain)
        os.rename(
            staging / BACKUP_PAYLOAD_DIRECTORY,
            destination / BACKUP_PAYLOAD_DIRECTORY,
        )
        _assert_directory_chain(backup_root_chain)
        os.rename(
            staging / BACKUP_MANIFEST_FILENAME,
            destination / BACKUP_MANIFEST_FILENAME,
        )
        staging.rmdir()
    except OSError as error:
        try:
            current_state = os.lstat(destination)
            if (
                _has_reparse_attribute(current_state)
                or not _same_stat_identity(reserved_state, current_state)
            ):
                raise OSError
            shutil.rmtree(destination)
        except OSError as cleanup_error:
            raise _BackupOperationFailure(
                BackupErrorCode.CLEANUP_FAILED,
                "O backup falhou e o destino incompleto não pôde ser removido.",
            ) from cleanup_error
        raise _BackupOperationFailure(
            BackupErrorCode.PUBLISH_FAILED,
            "Não foi possível concluir o backup.",
        ) from error


def _same_stat_identity(
    first: os.stat_result,
    second: os.stat_result,
) -> bool:
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _write_manifest(
    path: Path,
    manifest: BackupManifest,
    backup_root_chain: tuple[_PathIdentity, ...],
) -> None:
    serialized = json.dumps(
        _manifest_as_dict(manifest),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    try:
        _assert_directory_chain(backup_root_chain)
        _assert_directory_chain(_capture_directory_chain(path.parent))
        with path.open("x", encoding="utf-8", newline="\n") as manifest_file:
            manifest_file.write(serialized)
            manifest_file.write("\n")
            manifest_file.flush()
            os.fsync(manifest_file.fileno())
    except OSError as error:
        raise _BackupOperationFailure(
            BackupErrorCode.COPY_FAILED,
            "Não foi possível registrar o manifesto do backup.",
        ) from error


def _manifest_as_dict(manifest: BackupManifest) -> dict[str, object]:
    return {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "backup_id": manifest.backup_id,
        "slot_number": manifest.slot_number,
        "created_at_utc": manifest.created_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_count": manifest.file_count,
        "total_size_bytes": manifest.total_size_bytes,
        "files": [
            {
                "relative_path": file.relative_path,
                "size_bytes": file.size_bytes,
                "modified_at_ns": file.modified_at_ns,
                "sha256": file.sha256,
            }
            for file in manifest.files
        ],
    }


def _validate_staged_backup(staging: Path, manifest: BackupManifest) -> None:
    try:
        top_level_names = {entry.name for entry in os.scandir(staging)}
        if top_level_names != {BACKUP_MANIFEST_FILENAME, BACKUP_PAYLOAD_DIRECTORY}:
            raise ValueError

        manifest_content = json.loads(
            (staging / BACKUP_MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
        if manifest_content != _manifest_as_dict(manifest):
            raise ValueError

        payload = staging / BACKUP_PAYLOAD_DIRECTORY
        copied_entries = _inventory_source_slot(payload)
        copied_files = {
            entry.relative_path: entry
            for entry in copied_entries
            if not entry.is_directory
        }
        if set(copied_files) != {file.relative_path for file in manifest.files}:
            raise ValueError

        for file in manifest.files:
            copied = copied_files[file.relative_path]
            if copied.size_bytes != file.size_bytes:
                raise ValueError
            if _sha256_file(payload / Path(file.relative_path)) != file.sha256:
                raise ValueError
    except (_BackupOperationFailure, OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise _BackupOperationFailure(
            BackupErrorCode.VALIDATION_FAILED,
            "A validação do backup falhou; nenhum backup foi publicado.",
        ) from error


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(_COPY_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


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
