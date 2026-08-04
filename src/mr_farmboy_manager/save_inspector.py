"""Módulo de inspeção estrutural do save.

Este módulo fornece funcionalidades para inspecionar metadados de arquivos
sem interpretar dados específicos do jogo.
"""

from __future__ import annotations

import hashlib
import json
import zlib
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class DetectedFormat(Enum):
    """Formatos detectados no arquivo."""

    UNKNOWN = auto()
    ZIP = auto()
    GZIP = auto()
    SQLITE = auto()
    JSON_TEXTUAL = auto()
    XML_TEXTUAL = auto()
    BINARY_UNKNOWN = auto()


@dataclass(frozen=True)
class SaveInspectionResult:
    """Resultado da inspeção do save."""

    readable_file: bool
    detected_format: DetectedFormat
    inspection_success: bool
    total_size_bytes: int | None = None
    sha256_hash: str | None = None
    first_bytes_hex: str | None = None
    file_extension: str | None = None
    is_empty: bool = False
    error_message: str | None = None


def _calculate_sha256(data: bytes) -> str:
    """Calcula o hash SHA-256 de dados binários."""
    return hashlib.sha256(data).hexdigest()


def _detect_format(data: bytes, extension: Optional[str]) -> DetectedFormat:
    """Detecta o formato do arquivo baseado nos primeiros bytes e extensao."""
    if len(data) == 0:
        return DetectedFormat.BINARY_UNKNOWN

    # Verifica ZIP (PK header)
    if data[:4] == b'PK\x03\x04':
        return DetectedFormat.ZIP

    # Verifica GZIP (1f 8b)
    if data[:2] == b'\x1f\x8b':
        return DetectedFormat.GZIP

    # Verifica SQLite (SQLite format 3)
    if data[:6] == b'SQLite format 3' or data[:16].startswith(b'SQLite format'):
        return DetectedFormat.SQLITE

    # Verifica JSON textual
    try:
        text_data = data.decode('utf-8')
        json.loads(text_data[:500])  # Tenta parsar apenas os primeiros bytes
        if extension and extension.lower() in ('.json', ):
            return DetectedFormat.JSON_TEXTUAL
        # Se é texto legivel e pode ser JSON, assume JSON
        try:
            json.loads(text_data[:1000])
            return DetectedFormat.JSON_TEXTUAL
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass

    # Verifica XML textual (<?xml ou <?XML)
    try:
        text_data = data.decode('utf-8')
        if text_data.strip().startswith('<?xml') or text_data.strip().startswith('<?XML'):
            return DetectedFormat.XML_TEXTUAL
    except UnicodeDecodeError:
        pass

    # Verifica se é texto binário (pode ser JSON/XML com codificação diferente)
    try:
        for encoding in ['utf-16', 'latin-1', 'cp1252']:
            text_data = data.decode(encoding)
            try:
                json.loads(text_data[:500])
                return DetectedFormat.JSON_TEXTUAL
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
    except Exception:
        pass

    # Verifica se é texto legível (não binário puro)
    try:
        text_data = data.decode('utf-8', errors='replace')
        if _is_text_file(text_data):
            # Se não foi JSON/XML, assume XML se tiver tags comuns
            if any(tag in text_data for tag in ['<html', '<body', '<table', '<tr']):
                return DetectedFormat.XML_TEXTUAL
            return DetectedFormat.JSON_TEXTUAL
    except Exception:
        pass

    return DetectedFormat.BINARY_UNKNOWN


def _is_text_file(content: str) -> bool:
    """Verifica se o conteúdo parece ser um arquivo de texto."""
    # Contagem de caracteres não-imprimíveis (exceto quebras de linha e tabs)
    non_printable_count = sum(1 for c in content if not (c in '\t\n\r\f' or ord(c) > 31 and ord(c) < 127))
    total_chars = len(content)

    if total_chars == 0:
        return False

    # Arquivo de texto se menos de 5% dos caracteres forem não-imprimíveis (muito mais estrito)
    return (non_printable_count / total_chars) < 0.05


def inspect_save(path: str | Path) -> SaveInspectionResult:
    """Inspeciona o arquivo e retorna metadados estruturados.

    Esta função opera sobre um arquivo fornecido e retorna informações
    sobre o conteúdo, sem interpretar dados específicos do jogo.

    Args:
        path: Caminho do arquivo a inspecionar (str ou Path).

    Returns:
        SaveInspectionResult com metadados do arquivo.

    Raises:
        FileNotFoundError: Se o caminho apontar para diretório, não arquivo.
        PermissionError: Sem permissão para ler o arquivo.
        ValueError: Arquivo vazio.
    """
    file_path = Path(path)

    # Validação básica: deve apontar para um arquivo
    if not file_path.is_file():
        return SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            error_message=f"Caminho nao aponta para um arquivo valido: {path}"
        )

    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except PermissionError:
        return SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            error_message="Sem permissao para ler o arquivo"
        )
    except IOError as e:
        return SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            error_message=f"Erro ao ler arquivo: {e}"
        )

    # Validação de tamanho mínimo
    if len(data) < 1:
        return SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.BINARY_UNKNOWN,
            inspection_success=True,
            total_size_bytes=0,
            is_empty=True,
            error_message="Arquivo vazio"
        )

    try:
        # Calcula hash SHA-256
        sha256_hash = _calculate_sha256(data)

        # Primeiros 16 bytes em hexadecimal (32 caracteres)
        first_bytes_hex = data[:16].hex() if len(data) >= 16 else data.hex()

        # Extensão do arquivo
        file_extension = file_path.suffix.lower() or None

        # Detecta formato
        detected_format = _detect_format(data, file_extension)

        return SaveInspectionResult(
            readable_file=detected_format in (DetectedFormat.JSON_TEXTUAL, DetectedFormat.XML_TEXTUAL),
            detected_format=detected_format,
            inspection_success=True,
            total_size_bytes=len(data),
            sha256_hash=sha256_hash,
            first_bytes_hex=first_bytes_hex,
            file_extension=file_extension,
            is_empty=False,
            error_message=None
        )

    except Exception as e:
        return SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            total_size_bytes=len(data),
            file_extension=file_extension,
            error_message=f"Erro ao processar dados: {e}"
        )


def calculate_file_hash(path: str | Path) -> str:
    """Calcula o hash SHA-256 de um arquivo.

    Args:
        path: Caminho do arquivo (str ou Path).

    Returns:
        Hash SHA-256 hexadecimal do arquivo.

    Raises:
        FileNotFoundError: Se o caminho não for um arquivo válido.
        PermissionError: Sem permissão para ler o arquivo.
    """
    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(f"Caminho nao aponta para um arquivo valido: {path}")

    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def verify_file_integrity(original_path: str | Path, snapshot_path: str | Path) -> bool:
    """Verifica se os hashes de dois arquivos correspondem.

    Args:
        original_path: Caminho do arquivo original.
        snapshot_path: Caminho da cópia/snapshot.

    Returns:
        True se os hashes correspondem, False caso contrário.

    Raises:
        ValueError: Se um ou ambos os arquivos não existirem.
    """
    try:
        original_hash = calculate_file_hash(original_path)
        snapshot_hash = calculate_file_hash(snapshot_path)
        return original_hash == snapshot_hash
    except (FileNotFoundError, PermissionError) as e:
        raise ValueError(f"Erro ao verificar integridade: {e}") from e