"""Módulo de criação de snapshot seguro do save.

Este módulo fornece funcionalidades para criar cópias temporárias seguras
de arquivos, garantindo que o arquivo original nunca seja modificado.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


# Limite público para qualquer leitura/cópia de save externo.  Este valor é
# deliberadamente distinto do limite de 8 MiB de ``save_details``.
MAX_SAVE_FILE_SIZE_BYTES = 100 * 1024 * 1024
_READ_BLOCK_SIZE_BYTES = 64 * 1024
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class SaveFileSizeLimitError(ValueError):
    """O save ultrapassou o teto seguro de leitura."""

    def __init__(self) -> None:
        super().__init__("Arquivo acima do limite de leitura.")


class InvalidSaveFileSizeLimitError(ValueError):
    """O override tentou desativar ou elevar o teto público."""

    def __init__(self) -> None:
        super().__init__("Limite de leitura inválido.")


class UnsafeSaveFileError(ValueError):
    """O caminho não representa um arquivo regular estável e seguro."""

    def __init__(self) -> None:
        super().__init__("Arquivo de save inseguro.")


class SaveFileChangedError(ValueError):
    """O arquivo mudou enquanto o descritor estava em uso."""

    def __init__(self) -> None:
        super().__init__(
            "Integridade comprometida: arquivo alterado durante o tempo de leitura."
        )


def validate_max_size_bytes(max_size_bytes: object) -> int:
    """Aceita apenas inteiros positivos que reduzam o teto público."""
    if (
        type(max_size_bytes) is not int
        or max_size_bytes <= 0
        or max_size_bytes > MAX_SAVE_FILE_SIZE_BYTES
    ):
        raise InvalidSaveFileSizeLimitError()
    return max_size_bytes


def _is_reparse_or_symlink(state: object) -> bool:
    return stat.S_ISLNK(state.st_mode) or bool(
        getattr(state, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _same_identity(first: object, second: object) -> bool:
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _same_file_state(first: object, second: object) -> bool:
    return (
        _same_identity(first, second)
        and first.st_size == second.st_size
        and first.st_mtime_ns == second.st_mtime_ns
    )


def _absolute_path(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_reparse_components(path: Path) -> None:
    """Rejeita links/reparse points em qualquer componente já existente."""
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if not os.path.lexists(current):
            break
        if _is_reparse_or_symlink(os.lstat(current)):
            raise UnsafeSaveFileError()


def _inspect_file_boundary(
    path: str | Path, *, max_size_bytes: int
) -> tuple[Path, os.stat_result]:
    limit = validate_max_size_bytes(max_size_bytes)
    absolute_path = _absolute_path(path)
    _reject_reparse_components(absolute_path)
    boundary_state = os.lstat(absolute_path)
    if stat.S_ISDIR(boundary_state.st_mode):
        raise FileNotFoundError("Caminho aponta para um diretório, não para um arquivo.")
    if not stat.S_ISREG(boundary_state.st_mode) or _is_reparse_or_symlink(boundary_state):
        raise UnsafeSaveFileError()
    if boundary_state.st_size > limit:
        raise SaveFileSizeLimitError()
    return absolute_path, boundary_state


def get_safe_file_size(
    path: str | Path, *, max_size_bytes: int = MAX_SAVE_FILE_SIZE_BYTES
) -> int:
    """Obtém o tamanho somente após validar a fronteira sem seguir links."""
    _, boundary_state = _inspect_file_boundary(
        path, max_size_bytes=max_size_bytes
    )
    return boundary_state.st_size


def _open_read_descriptor(
    path: str | Path, *, max_size_bytes: int
) -> tuple[int, os.stat_result, Path]:
    """Abre uma vez e vincula o descritor à identidade vista na fronteira."""
    limit = validate_max_size_bytes(max_size_bytes)
    absolute_path, boundary_state = _inspect_file_boundary(
        path, max_size_bytes=limit
    )

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(absolute_path, flags)
        opened_state = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_state.st_mode)
            or _is_reparse_or_symlink(opened_state)
            or not _same_file_state(boundary_state, opened_state)
        ):
            raise UnsafeSaveFileError()
        if opened_state.st_size > limit:
            raise SaveFileSizeLimitError()
        result = (descriptor, opened_state, absolute_path)
        descriptor = None
        return result
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _descriptor_state(
    descriptor: int, initial_state: os.stat_result, max_size_bytes: int
) -> os.stat_result:
    """Valida somente metadados do descritor já aberto."""
    current_state = os.fstat(descriptor)
    if current_state.st_size > max_size_bytes:
        raise SaveFileSizeLimitError()
    if (
        not stat.S_ISREG(current_state.st_mode)
        or _is_reparse_or_symlink(current_state)
        or not _same_file_state(initial_state, current_state)
    ):
        raise SaveFileChangedError()
    return current_state


def _read_limited_descriptor(
    descriptor: int, initial_state: os.stat_result, *, max_size_bytes: int
) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total_size = 0
    while total_size < initial_state.st_size:
        block = os.read(
            descriptor,
            min(_READ_BLOCK_SIZE_BYTES, initial_state.st_size - total_size),
        )
        if not block:
            break
        chunks.append(block)
        total_size += len(block)
        _descriptor_state(descriptor, initial_state, max_size_bytes)

    final_state = _descriptor_state(descriptor, initial_state, max_size_bytes)
    if total_size != final_state.st_size:
        raise SaveFileChangedError()
    return b"".join(chunks)


def read_limited_file(path: str | Path, *, max_size_bytes: int = MAX_SAVE_FILE_SIZE_BYTES) -> bytes:
    """Lê um arquivo em blocos, sem materializar mais que ``max_size_bytes``.

    O tamanho é conferido antes, entre blocos e ao término, para detectar
    crescimento concorrente sem recorrer a ``read()`` sem limite.
    """
    limit = validate_max_size_bytes(max_size_bytes)
    descriptor, initial_state, _ = _open_read_descriptor(path, max_size_bytes=limit)
    try:
        return _read_limited_descriptor(
            descriptor, initial_state, max_size_bytes=limit
        )
    finally:
        os.close(descriptor)


def _copy_limited_file(
    source_descriptor: int,
    source_state: os.stat_result,
    destination_path: Path,
    *,
    max_size_bytes: int,
) -> tuple[int, str, os.stat_result]:
    """Copia e calcula o hash do save respeitando o limite em cada bloco."""
    source_hash = hashlib.sha256()
    total_size = 0

    os.lseek(source_descriptor, 0, os.SEEK_SET)
    with open(destination_path, "wb") as destination:
        while total_size < source_state.st_size:
            block = os.read(
                source_descriptor,
                min(_READ_BLOCK_SIZE_BYTES, source_state.st_size - total_size),
            )
            if not block:
                break
            destination.write(block)
            source_hash.update(block)
            total_size += len(block)
            _descriptor_state(source_descriptor, source_state, max_size_bytes)
        destination.flush()
        destination_state = os.fstat(destination.fileno())

    final_source_state = _descriptor_state(
        source_descriptor, source_state, max_size_bytes
    )
    if total_size != final_source_state.st_size or destination_state.st_size != total_size:
        raise SaveFileChangedError()
    return total_size, source_hash.hexdigest(), destination_state


@dataclass(frozen=True)
class SnapshotResult:
    """Resultado da criação de snapshot."""

    original_path: str
    snapshot_path: str
    size_bytes: int
    original_sha256: str
    snapshot_sha256: str


def _calculate_sha256_blocks(
    filepath: Path, *, max_size_bytes: int = MAX_SAVE_FILE_SIZE_BYTES
) -> str:
    """Calcula o hash SHA-256 de um arquivo lendo em blocos.

    Não carrega o arquivo inteiro em memória, calculando o hash em
    blocos de 64 KB. Isso permite processar arquivos grandes sem
    problemas de memória.

    Args:
        filepath: Caminho do arquivo a ser hashado.

    Returns:
        String hexadecimal com o hash SHA-256 (64 caracteres).
    """
    return calculate_limited_file_hash(filepath, max_size_bytes=max_size_bytes)


def _hash_limited_descriptor(
    descriptor: int, initial_state: os.stat_result, *, max_size_bytes: int
) -> str:
    sha256_hash = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    total_size = 0
    while total_size < initial_state.st_size:
        block = os.read(
            descriptor,
            min(_READ_BLOCK_SIZE_BYTES, initial_state.st_size - total_size),
        )
        if not block:
            break
        sha256_hash.update(block)
        total_size += len(block)
        _descriptor_state(descriptor, initial_state, max_size_bytes)
    final_state = _descriptor_state(descriptor, initial_state, max_size_bytes)
    if total_size != final_state.st_size:
        raise SaveFileChangedError()
    return sha256_hash.hexdigest()


def calculate_limited_file_hash(
    filepath: str | Path, *, max_size_bytes: int = MAX_SAVE_FILE_SIZE_BYTES
) -> str:
    """Calcula SHA-256 incremental sobre um único descritor estável."""
    limit = validate_max_size_bytes(max_size_bytes)
    descriptor, initial_state, _ = _open_read_descriptor(
        filepath, max_size_bytes=limit
    )
    try:
        return _hash_limited_descriptor(
            descriptor, initial_state, max_size_bytes=limit
        )
    finally:
        os.close(descriptor)


@contextmanager
def create_save_snapshot(
    original_path: str | Path, *, max_size_bytes: int = MAX_SAVE_FILE_SIZE_BYTES
) -> Iterator[SnapshotResult]:
    """Cria um snapshot seguro do arquivo original.

    Este context manager cria uma cópia temporária do arquivo em uma pasta
    temporária, garantindo que o arquivo original nunca seja modificado.
    O SHA-256 é verificado antes e após a cópia para garantir integridade.

    Args:
        original_path: Caminho do arquivo original (str ou Path).

    Yields:
        SnapshotResult com informações sobre a cópia e hashes SHA-256.

    Raises:
        FileNotFoundError: Se o caminho apontar para diretório, não arquivo.
        PermissionError: Sem permissão para ler ou criar cópia.
        ValueError: Arquivo vazio ou integridade comprometida.

    Notes:
        - O snapshot é removido automaticamente ao sair do contexto.
        - O hash SHA-256 do original e da cópia devem ser iguais.
        - Não deixa arquivos temporários após falha.
        - O tamanho e mtime do original são verificados antes e depois.
        - Alterações no arquivo original durante o uso do snapshot serão detectadas.
    """
    limit = validate_max_size_bytes(max_size_bytes)
    path = Path(original_path)

    # Inicializa todas as variáveis antes do try principal
    temp_dir: str | None = None
    snapshot_path_str: str | None = None
    source_descriptor: int | None = None
    original_stat_info: os.stat_result | None = None
    absolute_path: Path | None = None

    try:
        source_descriptor, original_stat_info, absolute_path = _open_read_descriptor(
            path, max_size_bytes=limit
        )

        # Validação de tamanho mínimo
        if original_stat_info.st_size < 1:
            raise ValueError("Arquivo vazio.")

    except FileNotFoundError:
        raise FileNotFoundError(f"Caminho não aponta para um arquivo válido: {path}")
    except IsADirectoryError:
        raise IsADirectoryError(f"Caminho aponta para um diretório, não para um arquivo: {path}") from None
    except PermissionError as e:
        raise PermissionError(f"Sem permissão para ler o arquivo original: {path}") from e

    try:
        # Cria pasta temporária usando mkdtemp com prefixo específico
        temp_dir = tempfile.mkdtemp(prefix="mr_farmboy_snapshot_")
        snapshot_path = Path(temp_dir) / path.name
        snapshot_path_str = str(snapshot_path.resolve())

        # Copia incrementalmente: jamais cria um snapshot acima do teto.
        copied_size, original_hash, snapshot_stat = _copy_limited_file(
            source_descriptor,
            original_stat_info,
            snapshot_path,
            max_size_bytes=limit,
        )
        snapshot_size = snapshot_stat.st_size

        # Verifica se o tamanho permanece inalterado
        if snapshot_size != original_stat_info.st_size or copied_size != original_stat_info.st_size:
            raise ValueError("Integridade comprometida: tamanho do arquivo alterado durante a cópia.")

        # Calcula hash da cópia (em blocos para arquivos grandes)
        snapshot_hash = _calculate_sha256_blocks(snapshot_path, max_size_bytes=limit)

        # Verifica integridade dos hashes (original antes e snapshot depois devem ser idênticos)
        if original_hash != snapshot_hash:
            raise ValueError("Integridade comprometida: hash do arquivo alterado durante a cópia.")

        size_bytes = snapshot_size

        yield SnapshotResult(
            original_path=str(absolute_path),
            snapshot_path=snapshot_path_str,
            size_bytes=size_bytes,
            original_sha256=original_hash,
            snapshot_sha256=snapshot_hash,
        )

        # APÓS YIELD: recalcula hash do original para garantir que não foi alterado durante o uso
        try:
            boundary_after_yield = os.lstat(absolute_path)
            if (
                _is_reparse_or_symlink(boundary_after_yield)
                or not _same_identity(original_stat_info, boundary_after_yield)
            ):
                raise SaveFileChangedError()
            _descriptor_state(source_descriptor, original_stat_info, limit)
            current_original_hash = _hash_limited_descriptor(
                source_descriptor,
                original_stat_info,
                max_size_bytes=limit,
            )
            if current_original_hash != original_hash:
                raise ValueError("Integridade comprometida: conteúdo do arquivo original foi alterado após snapshot.")

        except FileNotFoundError:
            raise FileNotFoundError(f"Arquivo desapareceu durante a operação: {path}")

    except PermissionError as error:
        raise PermissionError("Sem permissão para criar ou ler o snapshot.") from error

    finally:
        if source_descriptor is not None:
            try:
                os.close(source_descriptor)
            except OSError:
                pass
        # Remove a pasta temporária em TODOS os caminhos de saída (sucesso ou erro),
        # evitando vazamento de diretórios temporários. A exceção original, se houver,
        # continua propagando após a limpeza.
        if temp_dir is not None and Path(temp_dir).exists():
            try:
                # Não usa ignore_errors=True para detectar falha real na limpeza
                shutil.rmtree(temp_dir, ignore_errors=False)
            except FileNotFoundError:
                pass  # Já foi removido ou não existe mais
            except PermissionError as cleanup_error:
                raise RuntimeError(
                    f"Erro ao limpar diretório temporário {temp_dir}: permissão negada"
                ) from cleanup_error
            except OSError as cleanup_error:
                # Se já há uma exceção ativa, adiciona a falha de limpeza como causa
                if "Operation cancelled" not in str(cleanup_error):
                    raise RuntimeError(
                        f"Erro ao remover diretório temporário {temp_dir}: {cleanup_error}"
                    ) from cleanup_error
