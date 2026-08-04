"""Tests for the save_inspector module."""

import json
from pathlib import Path
import tempfile
import struct
import hashlib

import pytest

from mr_farmboy_manager.save_inspector import (
    inspect_save,
    calculate_file_hash,
    verify_file_integrity,
    DetectedFormat,
    SaveInspectionResult,
)


class TestInspectSave:
    """Tests for the inspect_save function."""

    def test_json_small(self, tmp_path: Path) -> None:
        """Verifica detecção de JSON pequeno."""
        json_file = tmp_path / "data.json"
        json_content = {'key': 'value', 'number': 42}

        json_file.write_text(json.dumps(json_content), encoding='utf-8')

        result = inspect_save(json_file)

        assert result.inspection_success is True
        assert result.is_textual is True
        assert result.detected_format == DetectedFormat.JSON_TEXTUAL
        assert result.total_size_bytes == len(json.dumps(json_content).encode('utf-8'))

    def test_json_large(self, tmp_path: Path) -> None:
        """Verifica detecção de JSON com mais de 1000 caracteres."""
        json_file = tmp_path / "large.json"
        # Gera JSON grande (>1000 chars) - array válido
        items = ['"item"'] * 500
        large_json = '[' + ','.join(items) + ']'

        json_file.write_bytes(large_json.encode('utf-8'))

        result = inspect_save(json_file)

        assert result.inspection_success is True
        assert result.is_textual is True
        assert result.detected_format == DetectedFormat.JSON_TEXTUAL
        assert result.total_size_bytes >= 1000

    def test_json_with_bom(self, tmp_path: Path) -> None:
        """Verifica detecção de JSON com BOM UTF-8."""
        json_file = tmp_path / "bom.json"
        # Adiciona BOM UTF-8 ao início do JSON
        bom_data = b'\xef\xbb\xbf' + json.dumps({'key': 'value'}).encode('utf-8')

        json_file.write_bytes(bom_data)

        result = inspect_save(json_file)

        # JSON com BOM deve ser detectado como texto
        assert result.inspection_success is True
        assert result.is_textual is True

    def test_json_invalid(self, tmp_path: Path) -> None:
        """Verifica que JSON inválido não é detectado como JSON mesmo com extensão .json."""
        json_file = tmp_path / "invalid.json"
        # JSON malformado
        invalid_content = '{"key": value'

        json_file.write_text(invalid_content, encoding='utf-8')

        result = inspect_save(json_file)

        assert result.inspection_success is True
        # JSON inválido não é detectado como JSON_TEXTUAL
        assert result.detected_format not in (DetectedFormat.JSON_TEXTUAL,)

    def test_common_text(self, tmp_path: Path) -> None:
        """Verifica detecção de texto comum."""
        text_file = tmp_path / "readme.txt"
        text_content = """This is a readme file.
It contains several lines of plain text.
No structured formatting here."""

        text_file.write_text(text_content, encoding='utf-8')

        result = inspect_save(text_file)

        assert result.inspection_success is True
        assert result.is_textual is True
        # Texto comum é detectado como TEXT_UNKNOWN (não JSON, não XML)
        assert result.detected_format == DetectedFormat.TEXT_UNKNOWN

    def test_xml_with_declaration(self, tmp_path: Path) -> None:
        """Verifica detecção de XML com declaração."""
        xml_file = tmp_path / "with_decl.xml"
        xml_content = '<?xml version="1.0"?><root><item>value</item></root>'

        xml_file.write_text(xml_content, encoding='utf-8')

        result = inspect_save(xml_file)

        assert result.inspection_success is True
        assert result.is_textual is True
        # XML com declaração é detectado especificamente como XML_DECLARATION
        assert result.detected_format == DetectedFormat.XML_DECLARATION

    def test_xml_no_declaration(self, tmp_path: Path) -> None:
        """Verifica detecção de XML sem declaração (como <root><item>1</item></root>)."""
        xml_file = tmp_path / "no_decl.xml"
        # XML sem declaração de namespace nem process instruction
        xml_content = '<root><item>value</item></root>'

        xml_file.write_text(xml_content, encoding='utf-8')

        result = inspect_save(xml_file)

        assert result.inspection_success is True
        assert result.is_textual is True
        # XML sem declaração é detectado especificamente como XML_NO_DECLARATION
        assert result.detected_format == DetectedFormat.XML_NO_DECLARATION

    def test_xml_invalid(self, tmp_path: Path) -> None:
        """Verifica que XML inválido não é detectado como XML."""
        xml_file = tmp_path / "invalid.xml"
        # XML malformado
        invalid_content = '<root><item>unterminated'

        xml_file.write_text(invalid_content, encoding='utf-8')

        result = inspect_save(xml_file)

        assert result.inspection_success is True
        # XML inválido não é detectado como XML
        assert result.detected_format not in (DetectedFormat.XML_DECLARATION, DetectedFormat.XML_NO_DECLARATION)

    def test_zip_local_file_header(self, tmp_path: Path) -> None:
        """Verifica detecção de ZIP pelo local-file header PK\x03\x04."""
        zip_file = tmp_path / "fake.zip"
        # Local file header real + minimal central directory
        local_header = b'PK\x03\x04'  # Local file header
        central_dir = b'PK\x01\x02'   # End of central directory marker
        zip_data = local_header + central_dir

        zip_file.write_bytes(zip_data)

        result = inspect_save(zip_file)

        assert result.inspection_success is True
        assert result.is_textual is False  # ZIP é binário
        assert result.total_size_bytes == len(zip_data)

    def test_zip_empty(self, tmp_path: Path) -> None:
        """Verifica detecção de ZIP vazio/end-of-central-directory."""
        zip_file = tmp_path / "empty.zip"
        # End of central directory record (PK\x05\x06)
        end_record = b'PK\x05\x06\x14\x00\x00\x00\x00\x00\x00\x00'

        zip_file.write_bytes(end_record)

        result = inspect_save(zip_file)

        assert result.inspection_success is True
        assert result.is_textual is False
        assert result.detected_format == DetectedFormat.ZIP

    def test_gzip(self, tmp_path: Path) -> None:
        """Verifica detecção de GZIP."""
        gzip_file = tmp_path / "test.gz"
        # Header do GZIP (1f 8b) + compressed data simulation
        gzip_data = b'\x1f\x8b' + b'\x08' + b'\x00\x00\x00\x00' + b'test data'

        gzip_file.write_bytes(gzip_data)

        result = inspect_save(gzip_file)

        assert result.inspection_success is True
        assert result.is_textual is False
        assert result.detected_format == DetectedFormat.GZIP

    def test_sqlite_complete_header(self, tmp_path: Path) -> None:
        """Verifica detecção de SQLite com cabeçalho completo."""
        sqlite_file = tmp_path / "test.db"
        # SQLite header canônico: "SQLite format 3\0" (16 bytes)
        sqlite_data = b'SQLite format 3\x00' + b'\x00' * 50

        sqlite_file.write_bytes(sqlite_data)

        result = inspect_save(sqlite_file)

        assert result.inspection_success is True
        assert result.is_textual is False
        assert result.detected_format == DetectedFormat.SQLITE

    def test_binary_unknown(self, tmp_path: Path) -> None:
        """Verifica detecção de binário desconhecido."""
        binary_file = tmp_path / "binary.bin"
        # Dados binários sem header reconhecível
        binary_data = b'\x90\x3d\xcd\xa1\xe6\x7a\x40' * 20

        binary_file.write_bytes(binary_data)

        result = inspect_save(binary_file)

        assert result.inspection_success is True
        assert result.is_textual is False
        assert result.detected_format == DetectedFormat.BINARY_UNKNOWN

    def test_empty_file(self, tmp_path: Path) -> None:
        """Verifica detecção de arquivo vazio."""
        empty_file = tmp_path / "empty.bin"
        empty_file.write_bytes(b'')

        result = inspect_save(empty_file)

        assert result.inspection_success is True
        assert result.readable_file is True  # Arquivo é legível (existe e foi lido)
        assert result.is_empty is True
        assert result.detected_format == DetectedFormat.EMPTY

    def test_one_byte_file(self, tmp_path: Path) -> None:
        """Verifica detecção de arquivo de um byte."""
        single_byte = tmp_path / "single.bin"
        single_byte.write_bytes(b'\x42')  # Byte único

        result = inspect_save(single_byte)

        assert result.inspection_success is True
        assert result.readable_file is True
        assert result.is_empty is False
        assert result.total_size_bytes == 1

    def test_nonexistent_path_result(self, tmp_path: Path) -> None:
        """Verifica resultado para caminho inexistente."""
        nonexistent = tmp_path / "does_not_exist.bin"

        result = inspect_save(nonexistent)

        assert result.inspection_success is False
        assert result.readable_file is False
        assert result.error_message is not None

    def test_directory_path_result(self, tmp_path: Path) -> None:
        """Verifica resultado quando caminho é diretório."""
        dir_path = tmp_path  # tmp_path já é um diretório

        result = inspect_save(dir_path)

        assert result.inspection_success is False
        assert result.readable_file is False
        assert result.error_message is not None

    def test_first_bytes_hex_32_chars(self, tmp_path: Path) -> None:
        """Verifica que first_bytes_hex tem exatamente 32 caracteres hexadecimais."""
        test_file = tmp_path / "bytes_test.bin"

        # Arquivo com mais de 16 bytes para garantir primeiros 16 sejam representados
        test_data = b'ABCDEFGHIJ0123456789abcdef!'
        test_file.write_bytes(test_data)

        result = inspect_save(test_file)

        assert result.first_bytes_hex is not None
        assert len(result.first_bytes_hex) == 32, f"Expected 32 chars, got {len(result.first_bytes_hex)}"
        # Verifica que são caracteres hex válidos
        assert all(c in '0123456789abcdef' for c in result.first_bytes_hex.lower())


class TestSaveInspectionResult:
    """Tests for SaveInspectionResult dataclass."""

    def test_result_structure_success(self) -> None:
        """Verifica estrutura de resultado com sucesso."""
        # Hash SHA-256 válido tem exatamente 64 caracteres hexadecimais
        sha256_hash = "a" * 32 + "b" * 32  # 64 chars

        result = SaveInspectionResult(
            readable_file=True,
            detected_format=DetectedFormat.JSON_TEXTUAL,
            inspection_success=True,
            is_empty=False,
            total_size_bytes=1234,
            sha256_hash=sha256_hash,
            first_bytes_hex="0" * 32,  # 16 bytes = 32 hex chars
            file_extension=".json",
            is_textual=True,
            error_message=None,
        )

        assert result.readable_file is True
        assert result.detected_format == DetectedFormat.JSON_TEXTUAL
        assert result.inspection_success is True
        assert result.total_size_bytes == 1234
        assert result.sha256_hash is not None
        assert len(result.sha256_hash) == 64, f"Expected 64 chars, got {len(result.sha256_hash)}"
        assert result.first_bytes_hex is not None
        assert len(result.first_bytes_hex) == 32, f"Expected 32 chars, got {len(result.first_bytes_hex)}"
        assert result.file_extension == ".json"
        assert result.is_empty is False
        assert result.error_message is None


class TestHashAndIntegrity:
    """Tests for hash calculation and integrity verification."""

    def test_calculate_file_hash(self, tmp_path: Path) -> None:
        """Verifica cálculo de hash SHA-256 de arquivo."""
        test_file = tmp_path / "hash_test.bin"
        test_data = b'Hash test data content'

        with open(test_file, 'wb') as f:
            f.write(test_data)

        result = calculate_file_hash(str(test_file))

        # Verifica que o hash é válido (64 chars hexadecimais)
        assert len(result) == 64
        assert all(c in '0123456789abcdef' for c in result.lower())

        # Calcula hash manualmente para comparação
        expected = hashlib.sha256(test_data).hexdigest()
        assert result == expected

    def test_verify_file_integrity_same_content(self, tmp_path: Path) -> None:
        """Verifica que arquivos idênticos retornam True."""
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"

        original_data = b'Integrity test data'
        with open(file1, 'wb') as f:
            f.write(original_data)
        with open(file2, 'wb') as f:
            f.write(original_data)

        result = verify_file_integrity(str(file1), str(file2))

        assert result is True

    def test_verify_file_integrity_different_content(self, tmp_path: Path) -> None:
        """Verifica que arquivos diferentes retornam False."""
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"

        with open(file1, 'wb') as f:
            f.write(b'Data version 1')
        with open(file2, 'wb') as f:
            f.write(b'Data version 2')

        result = verify_file_integrity(str(file1), str(file2))

        assert result is False
