"""Módulo de inspeção estrutural do save.

Este módulo fornece funcionalidades para inspecionar metadados de arquivos
sem interpretar dados específicos do jogo.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class DetectedFormat(Enum):
    """Formatos detectados no arquivo."""

    EMPTY = auto()
    UNKNOWN = auto()
    ZIP = auto()
    GZIP = auto()
    SQLITE = auto()
    JSON_TEXTUAL = auto()
    XML_DECLARATION = auto()
    XML_NO_DECLARATION = auto()
    TEXT_UNKNOWN = auto()
    BINARY_UNKNOWN = auto()


@dataclass(frozen=True)
class SaveInspectionResult:
    """Resultado da inspeção do save."""

    readable_file: bool
    detected_format: DetectedFormat
    inspection_success: bool
    is_empty: bool = False
    is_textual: bool = False
    total_size_bytes: int | None = None
    sha256_hash: str | None = None
    first_bytes_hex: str | None = None
    file_extension: str | None = None
    error_message: str | None = None


def _calculate_sha256(data: bytes) -> str:
    """Calcula o hash SHA-256 de dados binários."""
    return hashlib.sha256(data).hexdigest()


def _is_empty_file(data: bytes) -> bool:
    """Verifica se o arquivo está vazio."""
    return len(data) == 0


def _is_textual_content(content: str) -> bool:
    """Verifica se o conteúdo parece ser texto legível (não binário).

    Contagem de caracteres não-imprimíveis vs totais. Texto comum deve ter
    menos de 10% de caracteres que indicam dados binários.
    """
    if len(content) == 0:
        return True

    # Caracteres considerados indicadores de binário:
    # - Controles ASCII (< 32, exceto tabs/newlines permitidos)
    # - Bytes com alta ordem (128-255) que são comuns em dados binários
    non_printable = sum(1 for c in content if ord(c) < 32 and c not in '\t\n\r\f')
    high_bytes = sum(1 for c in content if ord(c) > 127)
    total_chars = len(content)

    # Soma ambos os tipos e verifica se < 10% do conteúdo
    suspicious_count = non_printable + high_bytes
    return (suspicious_count / total_chars) < 0.1


def _is_valid_json(data: bytes) -> bool:
    """Tenta validar JSON decodificado."""
    try:
        text_data = data.decode('utf-8')
        json.loads(text_data)
        return True
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False


def _is_valid_xml(data: bytes) -> DetectedFormat:
    """Tenta validar XML usando ElementTree.

    Retorna JSON_TEXTUAL se o texto for válido JSON mas não XML.
    Retorna EMPTY para arquivo vazio.
    Retorna XML_NO_DECLARATION para XML sem declaração.
    Retorna XML_DECLARATION para XML com declaração <?xml ...?>.
    Retorna TEXT_UNKNOWN se não for validado como XML.
    """
    if len(data) == 0:
        return DetectedFormat.EMPTY

    try:
        text_data = data.decode('utf-8')

        # Tenta parsear como XML completo (com ou sem declaração)
        root = ET.fromstring(text_data)

        # Verifica se tem declaração XML
        if text_data.lstrip().startswith('<?xml'):
            return DetectedFormat.XML_DECLARATION

        # XML sem declaração
        return DetectedFormat.XML_NO_DECLARATION

    except ET.ParseError:
        # Se não é XML, verifica se é texto legível JSON
        try:
            json.loads(text_data)
            return DetectedFormat.JSON_TEXTUAL
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Retorna TEXT_UNKNOWN para texto legível mas não estruturado
        if _is_textual_content(text_data):
            return DetectedFormat.TEXT_UNKNOWN

    except UnicodeDecodeError:
        # Tenta UTF-16 e latin-1
        try:
            text_data = data.decode('utf-16')
            root = ET.fromstring(text_data)
            if text_data.lstrip().startswith('<?xml'):
                return DetectedFormat.XML_DECLARATION
            return DetectedFormat.XML_NO_DECLARATION
        except ET.ParseError:
            pass

        try:
            text_data = data.decode('latin-1')
            if _is_textual_content(text_data):
                return DetectedFormat.TEXT_UNKNOWN
        except Exception:
            pass

    return DetectedFormat.BINARY_UNKNOWN


def _detect_format(data: bytes, extension: Optional[str]) -> DetectedFormat:
    """Detecta o formato do arquivo baseado nos primeiros bytes e conteúdo.

    A detecção prioriza cabeçalhos binários conhecidos (ZIP, GZIP, SQLite)
    antes de tentar parse como texto estruturado (JSON, XML).

    Args:
        data: Conteúdo binário do arquivo.
        extension: Extensão do arquivo (opcional, não usada como prova definitiva).

    Returns:
        Enum DetectedFormat com o formato identificado.
    """
    if _is_empty_file(data):
        return DetectedFormat.EMPTY

    # Detecta ZIP por cabeçalhos comuns
    # Local file header
    if data[:4] == b'PK\x03\x04':
        return DetectedFormat.ZIP
    # Central directory header or End of central directory record
    if data[:4] in (b'PK\x01\x02', b'PK\x05\x06'):
        return DetectedFormat.ZIP
    # Zip64 end of central directory locator
    if data[:4] == b'PK\x06\x07':
        return DetectedFormat.ZIP
    # Span header
    if data[:4] == b'PK\x07\x08':
        return DetectedFormat.ZIP

    # Detecta GZIP pelo magic number
    if data[:2] == b'\x1f\x8b':
        return DetectedFormat.GZIP

    # Detecta SQLite pelo cabeçalho canônico
    if data[:16] == b'SQLite format 3\x00':
        return DetectedFormat.SQLITE

    # Detecta JSON textual - deve ser JSON válido completo
    if _is_valid_json(data):
        return DetectedFormat.JSON_TEXTUAL

    # Detecta XML (com ou sem declaração)
    detected_xml = _is_valid_xml(data)

    # Retorna o formato XML detectado
    if detected_xml in (DetectedFormat.XML_DECLARATION, DetectedFormat.XML_NO_DECLARATION):
        return detected_xml

    # Verifica se é texto legível mas não estruturado
    if _is_textual_content(data.decode('utf-8', errors='replace')):
        return DetectedFormat.TEXT_UNKNOWN

    return DetectedFormat.BINARY_UNKNOWN


def inspect_save(path: str | Path) -> SaveInspectionResult:
    """Inspeciona o arquivo e retorna metadados estruturados.

    Esta função opera sobre um arquivo fornecido e retorna informações
    sobre o conteúdo, sem interpretar dados específicos do jogo.

    Args:
        path: Caminho do arquivo a inspecionar (str ou Path).

    Returns:
        SaveInspectionResult com metadados do arquivo.
    """
    file_path = Path(path)

    # Validação básica: deve apontar para um arquivo
    if not file_path.is_file():
        return SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            error_message=f"Caminho não aponta para um arquivo válido: {path}"
        )

    try:
        # Lê o conteúdo do arquivo (em modo binário)
        data = file_path.read_bytes()
    except PermissionError:
        return SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            error_message="Sem permissão para ler o arquivo"
        )
    except IOError as e:
        return SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            error_message=f"Erro ao ler arquivo: {e}"
        )

    # Validação de tamanho mínimo (arquivo deve ter pelo menos 1 byte)
    if len(data) < 1:
        return SaveInspectionResult(
            readable_file=True,
            detected_format=DetectedFormat.EMPTY,
            inspection_success=True,
            is_empty=True,
            error_message=None
        )

    try:
        # Calcula hash SHA-256 do arquivo
        sha256_hash = _calculate_sha256(data)

        # Primeiros 16 bytes em hexadecimal (32 caracteres)
        first_bytes_hex = data[:16].hex() if len(data) >= 16 else data.hex()

        # Extensão do arquivo (informativa, não determinante)
        file_extension = file_path.suffix.lower() or None

        # Detecta formato baseado no conteúdo
        detected_format = _detect_format(data, file_extension)

        # Determina se é textual baseado no formato detectado
        is_textual = detected_format in (
            DetectedFormat.JSON_TEXTUAL,
            DetectedFormat.XML_DECLARATION,
            DetectedFormat.XML_NO_DECLARATION,
            DetectedFormat.TEXT_UNKNOWN,
        )

        return SaveInspectionResult(
            readable_file=True,
            detected_format=detected_format,
            inspection_success=True,
            is_empty=False,
            is_textual=is_textual,
            total_size_bytes=len(data),
            sha256_hash=sha256_hash,
            first_bytes_hex=first_bytes_hex,
            file_extension=file_extension,
            error_message=None
        )

    except Exception as e:
        return SaveInspectionResult(
            readable_file=True,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            error_message=f"Erro durante inspeção: {e}"
        )


def verify_file_integrity(original_path: str | Path, snapshot_path: str | Path) -> bool:
    """Verifica se dois arquivos têm o mesmo conteúdo SHA-256.

    Compara os hashes SHA-256 do original e do snapshot para garantir
    que a cópia é idêntica ao original.

    Args:
        original_path: Caminho do arquivo original.
        snapshot_path: Caminho do arquivo de snapshot/cópia.

    Returns:
        True se os hashes forem idênticos, False caso contrário.
    """
    try:
        with open(original_path, 'rb') as f:
            original_hash = hashlib.sha256(f.read()).hexdigest()

        with open(snapshot_path, 'rb') as f:
            snapshot_hash = hashlib.sha256(f.read()).hexdigest()

        return original_hash == snapshot_hash
    except Exception:
        return False


def calculate_file_hash(filepath: str | Path) -> str:
    """Calcula o hash SHA-256 de um arquivo lendo em blocos.

    Não carrega o arquivo inteiro em memória, calculando o hash em
    blocos de 64 KB. Isso permite processar arquivos grandes sem
    problemas de memória.

    Args:
        filepath: Caminho do arquivo a ser hashado (str ou Path).

    Returns:
        String hexadecimal com o hash SHA-256 (64 caracteres).
    """
    sha256_hash = hashlib.sha256()
    block_size = 65536  # 64 KB por bloco
    path = Path(filepath)

    with open(path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256_hash.update(block)

    return sha256_hash.hexdigest()
