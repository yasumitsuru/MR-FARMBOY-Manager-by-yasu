"""Módulo de criação de snapshot seguro do save.

Este módulo fornece funcionalidades para criar cópias temporárias seguras
de arquivos, garantindo que o arquivo original nunca seja modificado.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class SnapshotResult:
    """Resultado da criação de snapshot."""

    original_path: str
    snapshot_path: str
    size_bytes: int
    original_sha256: str
    snapshot_sha256: str


def _calculate_sha256_blocks(filepath: Path) -> str:
    """Calcula o hash SHA-256 de um arquivo lendo em blocos.

    Não carrega o arquivo inteiro em memória, calculando o hash em
    blocos de 64 KB. Isso permite processar arquivos grandes sem
    problemas de memória.

    Args:
        filepath: Caminho do arquivo a ser hashado.

    Returns:
        String hexadecimal com o hash SHA-256 (64 caracteres).
    """
    sha256_hash = hashlib.sha256()
    block_size = 65536  # 64 KB por bloco

    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256_hash.update(block)

    return sha256_hash.hexdigest()


@contextmanager
def create_save_snapshot(original_path: str | Path) -> Iterator[SnapshotResult]:
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
    path = Path(original_path)

    # Inicializa todas as variáveis antes do try principal
    temp_dir: str | None = None
    snapshot_path_str: str | None = None
    original_stat_info: os.stat_result | None = None
    original_mtime_ns_before: int | 0 = 0
    original_size_bytes_before: int | 0 = 0

    try:
        # Verifica se é diretório antes de tentar ler (evita confusão com Permiss�oError no Windows)
        if path.is_dir():
            raise FileNotFoundError(f"Caminho aponta para um diretório, não para um arquivo: {path}")

        # Tenta ler o arquivo - FileNotFoundError para inexistentes
        original_data = path.read_bytes()

        # Validação de tamanho mínimo
        if len(original_data) < 1:
            raise ValueError("Arquivo vazio.")

        original_size_bytes_before = len(original_data)
        original_stat_info = path.stat()
        original_mtime_ns_before = original_stat_info.st_mtime_ns

        # Calcula hash do original (em blocos para arquivos grandes)
        original_hash = _calculate_sha256_blocks(path)

    except FileNotFoundError:
        raise FileNotFoundError(f"Caminho não aponta para um arquivo válido: {path}")
    except IsADirectoryError:
        # Tratar explicitamente caminhos que apontam para diretórios
        raise IsADirectoryError(f"Caminho aponta para um diretório, não para um arquivo: {path}") from None
    except PermissionError as e:
        raise PermissionError(f"Sem permissão para ler o arquivo original: {path}") from e
    except IOError as e:
        raise PermissionError(f"Erro ao acessar arquivo original: {e}") from e

    try:
        # Cria pasta temporária usando mkdtemp com prefixo específico
        temp_dir = tempfile.mkdtemp(prefix="mr_farmboy_snapshot_")
        snapshot_path = Path(temp_dir) / path.name
        snapshot_path_str = str(snapshot_path.resolve())

        # Copia o arquivo com metadados preservados (shutil.copy2)
        shutil.copy2(path, snapshot_path)

        # Lê a cópia para verificar integridade antes de yield
        snapshot_data = snapshot_path.read_bytes()

        # Verifica se o tamanho permanece inalterado
        if len(snapshot_data) != original_size_bytes_before:
            raise ValueError("Integridade comprometida: tamanho do arquivo alterado durante a cópia.")

        # Verifica se o mtime (tempo de modificação) permanece inalterado
        stat_info_after = path.stat()
        mtime_ns_after = stat_info_after.st_mtime_ns
        if mtime_ns_after != original_mtime_ns_before:
            raise ValueError("Integridade comprometida: tempo de modificação do arquivo alterado.")

        # Calcula hash da cópia
        snapshot_hash = _calculate_sha256_blocks(snapshot_path)

        # Verifica integridade dos hashes (original antes e snapshot depois devem ser idênticos)
        if original_hash != snapshot_hash:
            raise ValueError("Integridade comprometida: hash do arquivo alterado durante a cópia.")

        size_bytes = len(snapshot_data)

        yield SnapshotResult(
            original_path=str(path.resolve()),
            snapshot_path=snapshot_path_str,
            size_bytes=size_bytes,
            original_sha256=original_hash,
            snapshot_sha256=snapshot_hash,
        )

        # APÓS YIELD: recalcula hash do original para garantir que não foi alterado durante o uso
        current_original_data = path.read_bytes()
        if len(current_original_data) != original_size_bytes_before:
            raise ValueError("Integridade comprometida: tamanho do arquivo original foi alterado após snapshot.")

        current_original_hash = _calculate_sha256_blocks(path)
        if current_original_hash != original_hash:
            raise ValueError("Integridade comprometida: conteúdo do arquivo original foi alterado após snapshot.")

    except FileNotFoundError:
        # Se o arquivo sumiu durante a cópia ou verificação, lança FileNotFoundError
        raise FileNotFoundError(f"Arquivo desapareceu durante a operação: {path}")
    except Exception:
        # Limpa pasta temporária em caso de erro (sem silenciar falhas)
        try:
            if temp_dir is not None and Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            # Se não houver exceção ativa, reporta a falha de limpeza
            raise RuntimeError(f"Erro ao limpar diretório temporário {temp_dir}: {e}") from e
        raise

    finally:
        # Sempre remove pasta temporária ao sair do contexto (após yield)
        if temp_dir is not None and Path(temp_dir).exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=False)
            except FileNotFoundError:
                pass  # Já foi removido por outra exceção
            except PermissionError:
                raise RuntimeError(f"Erro ao remover diretório temporário {temp_dir}: permissão negada") from None
            except OSError as e:
                raise RuntimeError(f"Erro ao remover diretório temporário {temp_dir}: {e}") from e
