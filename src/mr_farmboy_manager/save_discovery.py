"""Módulo de descoberta estrutural sanitizada de saves reais - Tarefa 2.3."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import sqlite3
import shutil
import zipfile
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from .save_snapshot import create_save_snapshot


class SavedFormat(Enum):
    """Formatos detectados no arquivo.

    Alias para compatibilidade com o módulo save_inspector que usa DetectedFormat.
    """

    EMPTY = auto()
    UNKNOWN = auto()
    ZIP = auto()
    GZIP = auto()
    SQLITE = auto()
    JSON_OBJECT = auto()
    JSON_ARRAY = auto()
    JSON_PRIMITIVE = auto()
    XML_VALID = auto()
    BINARY_UNKNOWN = auto()


# Alias para compatibilidade com o módulo save_inspector
DetectedFormat = SavedFormat


@dataclass(frozen=True)
class SaveDiscoveryResult:
    """Resultado da descoberta estrutural sanitizada do save.

    Contém apenas metadados agregados e tipados, sem caminhos absolutos,
    nomes internos sensíveis ou conteúdo bruto.
    """

    success: bool
    detected_format: SavedFormat
    size_bytes: int | None = None
    file_extension: str | None = None
    is_empty: bool = False
    is_textual: bool = False
    container_entries_count: int | None = None
    sqlite_table_count: int | None = None
    top_level_json_type: str | None = None
    xml_root_tag_present: bool | None = None
    compression_detected: bool = False
    sanitized_notes: tuple[str, ...] = field(default_factory=tuple)
    error_message: str | None = None


# LIMITES DE SEGURANÇA
MAX_ZIP_ENTRIES = 1000
MAX_DECOMPRESSED_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_ENTRY_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB por entrada


def _estimate_textual_ratio(content: str) -> float:
    """Estima a proporção de caracteres imprimíveis no conteúdo."""
    if not content:
        return 1.0
    printable = sum(1 for c in content if ord(c) >= 32 or c in '\t\n\r\f')
    return printable / len(content)


def _is_zip_file(data: bytes) -> bool:
    """Detecta se os dados representam um arquivo ZIP válido."""
    sigs = [b'PK\x03\x04', b'PK\x01\x02', b'PK\x05\x06', b'PK\x06\x07', b'PK\x07\x08']
    return len(data) >= 4 and data[:4] in sigs


def _is_gzip_file(data: bytes) -> bool:
    """Detecta se os dados representam um arquivo GZIP válido."""
    return len(data) >= 2 and data[:2] == b'\x1f\x8b'


def _is_sqlite_file(data: bytes) -> bool:
    """Detecta se os dados representam um arquivo SQLite válido."""
    return len(data) >= 16 and data[:16] == b'SQLite format 3\x00'


def _validate_zip_structure(zip_path: str | Path) -> tuple[int, bool]:
    """Valida e conta entradas de ZIP com limites de segurança.

    Returns:
        Tupla (count_de_entradas, criptografado).

    Raises:
        ValueError: Se o ZIP exceder limites críticos de segurança.
    """
    try:
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            total_decompressed = 0
            is_encrypted = False
            entry_count = 0

            for info in zf.infolist():
                if info.flag_bits & 0x1:
                    is_encrypted = True
                if info.compress_size > MAX_ENTRY_SIZE_BYTES:
                    raise ValueError("Entrada ZIP excessivamente grande")
                total_decompressed += info.compress_size
                entry_count += 1

                # Limitar contagem para evitar problemas de desempenho
                if entry_count > MAX_ZIP_ENTRIES + 10:
                    break

            # Ajustar o resultado final com os limites aplicados
            actual_count = min(entry_count, MAX_ZIP_ENTRIES)

            return actual_count, is_encrypted
    except zipfile.BadZipFile:
        raise ValueError("Arquivo não é um ZIP válido")


def _get_aggregated_extensions(zip_path: str | Path) -> set[str]:
    """Obtém extensões agregadas de entradas ZIP sem expor nomes."""
    extensions = set()
    try:
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            for info in zf.infolist():
                if info.file_size > 0 and b'.' in info.filename:
                    last_dot = info.filename.rfind('.')
                    if last_dot > 0:
                        extensions.add(info.filename[last_dot + 1:].lower())
    except Exception:
        pass
    return extensions


def _try_decompress_gzip(data: bytes, max_output: int = 64 * 1024) -> str | None:
    """Tenta descomprimir uma amostra limitada de GZIP."""
    try:
        compressed = data[:8192]
        import io
        decompressor = gzip.GzipFile(fileobj=io.BytesIO(compressed), mode='rb')
        decompressed = decompressor.read(max_output)
        decompressor.close()
        if len(decompressed) == 0:
            return None
        try:
            return decompressed.decode('utf-8', errors='ignore')
        except UnicodeDecodeError:
            return None
    except Exception:
        return None


def _validate_sqlite_structure(snapshot_path: str | Path) -> int | None:
    """Valida e conta tabelas SQLite com modo somente leitura."""
    try:
        conn = sqlite3.connect(f'file:{snapshot_path}?mode=ro', uri=True, timeout=1.0)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table_count = len(cursor.fetchall())
        conn.close()
        return table_count
    except sqlite3.Error:
        raise ValueError("Arquivo não é um SQLite válido")


def _validate_json_structure(data: bytes) -> tuple[str | None, bool]:
    """Valida estrutura JSON e retorna tipo do nível superior."""
    try:
        text = data.lstrip(b'\xef\xbb\xbf').decode('utf-8')
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return 'object', True
        elif isinstance(parsed, list):
            return 'array', True
        elif isinstance(parsed, (str, int, float, bool)):
            return type(parsed).__name__, True
        elif parsed is None:
            return 'null', True
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return None, False


def _discover_format(data: bytes) -> SavedFormat:
    """Detecta formato baseado no conteúdo."""
    if len(data) == 0:
        return SavedFormat.EMPTY
    if _is_sqlite_file(data):
        return SavedFormat.SQLITE
    if _is_zip_file(data):
        return SavedFormat.ZIP
    if _is_gzip_file(data):
        return SavedFormat.GZIP

    try:
        text = data.lstrip(b'\xef\xbb\xbf').decode('utf-8')
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return SavedFormat.JSON_OBJECT
        elif isinstance(parsed, list):
            return SavedFormat.JSON_ARRAY
    except Exception:
        pass

    try:
        text = data.lstrip(b'\xef\xbb\xbf').decode('utf-8')
        import xml.etree.ElementTree as ET
        if text.strip():
            ET.fromstring(text)
            return SavedFormat.XML_VALID
    except Exception:
        pass

    try:
        content = data.decode('utf-8', errors='ignore')
        if _estimate_textual_ratio(content) >= 0.9:
            return SavedFormat.BINARY_UNKNOWN
    except Exception:
        pass
    return SavedFormat.UNKNOWN


def discover_save_structure(save_path: str | Path) -> SaveDiscoveryResult:
    """Descobre a estrutura sanitizada de um save local sem modificá-lo.

    Args:
        save_path: Caminho local do arquivo a ser inspecionado.

    Returns:
        SaveDiscoveryResult com metadados sanitizados e tipados.
    """
    path = Path(save_path)

    if not path.exists():
        return SaveDiscoveryResult(
            success=False, detected_format=SavedFormat.UNKNOWN, error_message="Caminho inválido"
        )
    if not path.is_file():
        return SaveDiscoveryResult(
            success=False, detected_format=SavedFormat.UNKNOWN, error_message="Diretório, não arquivo"
        )

    try:
        initial_size = path.stat().st_size
    except PermissionError:
        return SaveDiscoveryResult(
            success=False, detected_format=SavedFormat.UNKNOWN, error_message="Sem permissão"
        )

    if initial_size < 1:
        return SaveDiscoveryResult(
            success=True, detected_format=SavedFormat.EMPTY, size_bytes=0,
            file_extension=path.suffix.lower() or None, is_empty=True
        )

    with create_save_snapshot(save_path) as snapshot_info:
        snapshot_path = snapshot_info.snapshot_path

        try:
            with open(snapshot_path, 'rb') as f:
                data = f.read()

        except PermissionError:
            return SaveDiscoveryResult(
                success=False, detected_format=SavedFormat.UNKNOWN,
                error_message="Sem permissao para ler o arquivo"
            )

        try:
            size_bytes = len(data)
            detected_format = _discover_format(data)
            compression_detected = detected_format in (SavedFormat.ZIP, SavedFormat.GZIP)

            container_entries_count = None
            sqlite_table_count = None
            top_level_json_type = None
            xml_root_tag_present = None
            sanitized_notes: list[str] = []
            is_textual = False

            if detected_format == SavedFormat.ZIP:
                entry_count, _ = _validate_zip_structure(snapshot_path)
                container_entries_count = entry_count
                extensions = _get_aggregated_extensions(snapshot_path)
                sanitized_notes.append(f"ZIP com {entry_count} entradas")
                if extensions:
                    sanitized_notes.append(f"Extensoes: {', '.join(sorted(extensions))}")

            elif detected_format == SavedFormat.GZIP:
                sample_text = _try_decompress_gzip(data)
                if sample_text:
                    is_textual = _estimate_textual_ratio(sample_text) >= 0.8
                else:
                    is_textual = False

            elif detected_format == SavedFormat.SQLITE:
                table_count = _validate_sqlite_structure(snapshot_path)
                sqlite_table_count = table_count
                sanitized_notes.append(f"SQLite com {table_count} tabela(s)")

            elif detected_format in (SavedFormat.JSON_OBJECT, SavedFormat.JSON_ARRAY):
                json_type, is_valid = _validate_json_structure(data)
                top_level_json_type = json_type
                is_textual = is_valid
                if is_valid:
                    sanitized_notes.append(f"JSON nivel superior: {json_type}")

            elif detected_format == SavedFormat.XML_VALID:
                xml_root_tag_present = True
                is_textual = True
                sanitized_notes.append("XML estruturado valido")

            # Verificacao adicional de textualidade
            if not is_textual and data:
                try:
                    text_sample = data[:4096].decode('utf-8', errors='ignore')
                    if _estimate_textual_ratio(text_sample) >= 0.7:
                        is_textual = True
                        sanitized_notes.append("Conteudo textual legivel detectado")
                except Exception:
                    pass

            return SaveDiscoveryResult(
                success=True, detected_format=detected_format, size_bytes=size_bytes,
                file_extension=path.suffix.lower(), is_empty=False if data else True,
                is_textual=is_textual, container_entries_count=container_entries_count,
                sqlite_table_count=sqlite_table_count, top_level_json_type=top_level_json_type,
                xml_root_tag_present=xml_root_tag_present, compression_detected=compression_detected,
                sanitized_notes=tuple(sanitized_notes)
            )

        finally:
            try:
                if snapshot_path and Path(snapshot_path).exists():
                    parent = Path(snapshot_path).parent
                    shutil.rmtree(parent, ignore_errors=False)
            except Exception:
                pass


def format_sanitized_report(result: SaveDiscoveryResult) -> str:
    """Formata um relatorio sanitizado do resultado da descoberta."""
    lines = []

    status = "SUCESSO" if result.success else "FALHA"
    lines.append(f"Status: {status}")

    if not result.success:
        lines.append(f"Mensagem: {result.error_message or 'Erro desconhecido'}")
        return "\n".join(lines)

    lines.append("\n=== INFORMACOES BASICAS ===")
    size_str = f"{result.size_bytes} bytes" if result.size_bytes else "N/A"
    lines.extend([
        f"Tamanho: {size_str}",
        f"Formato: {result.detected_format.name}",
        f"Extensao: {result.file_extension or 'N/A'}",
        f"Classificacao: {'Texto legivel' if result.is_textual else 'Conteudo binario'}"
    ])

    lines.append("\n=== DETALHES ESTRUTURAIS ===")

    if result.detected_format == SavedFormat.ZIP and result.container_entries_count is not None:
        lines.extend([
            f"ZIP: {result.container_entries_count} entradas (nomes nao expostos)",
            "Comprimido: Sim",
            "Limites aplicados: maximo 1000 entradas, 100 MB descompactado"
        ])

    elif result.detected_format == SavedFormat.SQLITE and result.sqlite_table_count is not None:
        lines.append(f"SQLite: {result.sqlite_table_count} tabela(s) (nomes nao expostos)")

    elif result.detected_format in (SavedFormat.JSON_OBJECT, SavedFormat.JSON_ARRAY):
        json_type = result.top_level_json_type or 'N/A'
        lines.extend([
            f"JSON nivel superior: {json_type}",
            "Chaves e valores nao expostos para privacidade"
        ])

    elif result.detected_format == SavedFormat.XML_VALID:
        lines.append("XML estruturado com parsing seguro (tags raiz nao expostas)")

    elif result.detected_format == SavedFormat.BINARY_UNKNOWN:
        lines.append("Binario desconhecido ou com conteudo textual legivel")

    elif result.detected_format == SavedFormat.EMPTY:
        lines.append("Arquivo vazio (< 1 byte)")

    if result.sanitized_notes:
        lines.append("\n=== NOTAS SANITIZADAS ===")
        for note in result.sanitized_notes:
            lines.append(f"- {note}")

    lines.extend([
        "\n=== LIMITACOES DA INSPECCAO ===",
        "Inspeccao estrutural - dados especificos do jogo nao sao analisados.",
        "",
        "Proximo passo: Implementar parsing especific conforme necessario"
    ])

    return "\n".join(lines)


__all__ = [
    'SaveDiscoveryResult',
    'SavedFormat as SaveDiscoverySavedFormat',
    'discover_save_structure',
    'format_sanitized_report'
]
