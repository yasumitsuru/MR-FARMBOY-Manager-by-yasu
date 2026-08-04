"""Módulo de criação de snapshot seguro do save.

Este módulo fornece funcionalidades para criar cópias temporárias seguras
de arquivos, garantindo que o arquivo original nunca seja modificado.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
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


@contextmanager
def create_save_snapshot(original_path: str | Path) -> Iterator[SnapshotResult]:
    """Cria um snapshot seguro do arquivo original.

    Este context manager cria uma cópia temporária do arquivo em uma pasta
    temporária, garantindo que o arquivo original nunca seja modificado.

    Args:
        original_path: Caminho do arquivo original (str ou Path).

    Yields:
        SnapshotResult com informações sobre a cópia e hashes SHA-256.

    Raises:
        FileNotFoundError: Se o caminho apontar para diretório, não arquivo.
        PermissionError: Sem permissão para ler ou criar cópia.
        ValueError: Arquivo vazio.

    Notes:
        - O snapshot é removido automaticamente ao sair do contexto.
        - O hash SHA-256 do original e da cópia devem ser iguais.
        - Não deixa arquivos temporários após falha.
    """
    path = Path(original_path)

    # Validação básica: deve apontar para um arquivo
    if not path.is_file():
        raise FileNotFoundError(f"Caminho nao aponta para um arquivo valido: {path}")

    try:
        # Lê o conteúdo original sem modificar
        with open(path, "rb") as f:
            original_data = f.read()

        # Validação de tamanho mínimo
        if len(original_data) < 1:
            raise ValueError("Arquivo vazio.")

        # Calcula hash do original antes da cópia
        original_hash = hashlib.sha256(original_data).hexdigest()

    except (PermissionError, IOError) as e:
        raise PermissionError(f"Sem permissao para ler o arquivo original: {path}") from e

    try:
        # Cria pasta temporária
        temp_dir = tempfile.mkdtemp(prefix="mr_farmboy_snapshot_")
        snapshot_path = Path(temp_dir) / path.name

        # Copia o arquivo com metadados preservados (shutil.copy2)
        with open(path, "rb") as src:
            with open(snapshot_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        # Lê a cópia para calcular hash
        with open(snapshot_path, "rb") as f:
            snapshot_data = f.read()

        snapshot_hash = hashlib.sha256(snapshot_data).hexdigest()

        # Verifica integridade dos hashes
        if original_hash != snapshot_hash:
            raise ValueError("Hashes nao correspondem. Falha na copia.")

        size_bytes = len(snapshot_data)

        yield SnapshotResult(
            original_path=str(path.resolve()),
            snapshot_path=str(snapshot_path.resolve()),
            size_bytes=size_bytes,
            original_sha256=original_hash,
            snapshot_sha256=snapshot_hash,
        )

    except Exception:
        # Limpa pasta temporária em caso de erro
        try:
            import shutil as sh
            if Path(temp_dir).exists():
                sh.rmtree(temp_dir)
        except Exception:
            pass
        raise

    finally:
        # Sempre remove pasta temporária ao sair do contexto
        try:
            import shutil as sh
            if Path(temp_dir).exists():
                sh.rmtree(temp_dir)
        except Exception:
            pass