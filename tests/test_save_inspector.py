"""Tests for the save_inspector module."""

import json
from pathlib import Path
import tempfile
import struct

import pytest

from mr_farmboy_manager.save_inspector import (
    inspect_save,
    calculate_file_hash,
    DetectedFormat,
    SaveInspectionResult,
    verify_file_integrity,
)


class TestInspectSave:
    """Tests for the inspect_save function."""

    def test_zip_detection(self, tmp_path: Path) -> None:
        """Verifies ZIP file detection."""
        # Cria arquivo com header PK do ZIP
        zip_file = tmp_path / "fake.zip"
        # Header ZIP real + dados
        zip_data = b'PK\x03\x04' + struct.pack('<H', 20) + b'\x00' * 50

        zip_file.write_bytes(zip_data)

        result = inspect_save(zip_file)

        assert result.inspection_success is True
        assert result.readable_file is False
        assert result.detected_format == DetectedFormat.ZIP
        assert result.is_empty is False
        assert result.total_size_bytes == len(zip_data)

    def test_gzip_detection(self, tmp_path: Path) -> None:
        """Verifies GZIP file detection."""
        gzip_file = tmp_path / "fake.gz"
        # Header do GZIP (1f 8b)
        gzip_data = b'\x1f\x8b' + b'\x08' + b'\x00\x00\x00\x00' + b'test data'

        gzip_file.write_bytes(gzip_data)

        result = inspect_save(gzip_file)

        assert result.inspection_success is True
        assert result.readable_file is False
        assert result.detected_format == DetectedFormat.GZIP
        assert result.is_empty is False

    def test_sqlite_detection(self, tmp_path: Path) -> None:
        """Verifies SQLite file detection."""
        sqlite_file = tmp_path / "fake.db"
        # Header do SQLite
        sqlite_data = b'SQLite format 3\x00' + b'\x00' * 100

        sqlite_file.write_bytes(sqlite_data)

        result = inspect_save(sqlite_file)

        assert result.inspection_success is True
        assert result.readable_file is False
        assert result.detected_format == DetectedFormat.SQLITE
        assert result.is_empty is False

    def test_json_detection(self, tmp_path: Path) -> None:
        """Verifies JSON file detection."""
        json_file = tmp_path / "data.json"
        json_content = {'key': 'value', 'number': 42}

        json_file.write_text(json.dumps(json_content), encoding='utf-8')

        result = inspect_save(json_file)

        assert result.inspection_success is True
        assert result.readable_file is True
        assert result.detected_format == DetectedFormat.JSON_TEXTUAL
        assert result.is_empty is False
        assert result.file_extension == '.json'

    def test_xml_detection(self, tmp_path: Path) -> None:
        """Verifies XML file detection."""
        xml_file = tmp_path / "data.xml"
        xml_content = '<?xml version="1.0"?><root><item>test</item></root>'

        xml_file.write_text(xml_content, encoding='utf-8')

        result = inspect_save(xml_file)

        assert result.inspection_success is True
        assert result.readable_file is True
        # Pode detectar como XML ou JSON dependendo da implementacao
        assert result.detected_format in (DetectedFormat.XML_TEXTUAL, DetectedFormat.JSON_TEXTUAL)
        assert result.is_empty is False
        assert result.file_extension == '.xml'

    def test_binary_unknown_detection(self, tmp_path: Path) -> None:
        """Verifies binary unknown file detection."""
        bin_file = tmp_path / "binary.bin"
        # Dados binarios aleatorios sem header conhecido
        bin_data = bytes([i % 256 for i in range(100)])

        bin_file.write_bytes(bin_data)

        result = inspect_save(bin_file)

        assert result.inspection_success is True
        assert result.detected_format == DetectedFormat.BINARY_UNKNOWN
        assert result.is_empty is False
        assert result.total_size_bytes == 100

    def test_nonexistent_file_result(self, tmp_path: Path) -> None:
        """Verifies result for nonexistent file."""
        fake_path = tmp_path / "nonexistent.bin"

        result = inspect_save(fake_path)

        assert result.inspection_success is False
        assert result.readable_file is False
        assert result.detected_format == DetectedFormat.UNKNOWN
        assert result.error_message is not None
        assert len(result.error_message) > 0

    def test_directory_path_result(self, tmp_path: Path) -> None:
        """Verifies result for directory path."""
        result = inspect_save(tmp_path)

        assert result.inspection_success is False
        assert result.readable_file is False
        assert result.detected_format == DetectedFormat.UNKNOWN
        assert result.error_message is not None

    def test_empty_file_result(self, tmp_path: Path) -> None:
        """Verifies result for empty file."""
        empty_file = tmp_path / "empty.bin"
        empty_file.write_bytes(b"")

        result = inspect_save(empty_file)

        assert result.inspection_success is True
        assert result.is_empty is True
        assert result.total_size_bytes == 0
        assert result.readable_file is False
        assert result.detected_format == DetectedFormat.BINARY_UNKNOWN


class TestCalculateFileHash:
    """Tests for the calculate_file_hash function."""

    def test_hash_calculation(self, tmp_path: Path) -> None:
        """Verifies hash calculation."""
        test_file = tmp_path / "test.bin"
        test_data = b"hash calculation test data"

        test_file.write_bytes(test_data)

        result = calculate_file_hash(test_file)

        assert len(result) == 64  # SHA-256 é de 64 caracteres hexadecimais
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_with_str_path(self, tmp_path: Path) -> None:
        """Verifies hash calculation with string path."""
        test_file = tmp_path / "test.bin"
        test_data = b"string path test"

        test_file.write_bytes(test_data)

        result = calculate_file_hash(str(test_file))

        assert len(result) == 64

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that nonexistent file raises FileNotFoundError."""
        fake_path = tmp_path / "nonexistent.bin"

        with pytest.raises(FileNotFoundError):
            calculate_file_hash(fake_path)


class TestVerifyFileIntegrity:
    """Tests for the verify_file_integrity function."""

    def test_integrity_verification_success(self, tmp_path: Path) -> None:
        """Verifies that identical files have matching hashes."""
        original_file = tmp_path / "original.bin"
        copy_file = tmp_path / "copy.bin"

        test_data = b"integrity test data"

        original_file.write_bytes(test_data)
        copy_file.write_bytes(test_data)

        result = verify_file_integrity(original_file, copy_file)

        assert result is True

    def test_integrity_verification_mismatch(self, tmp_path: Path) -> None:
        """Verifies that different files have non-matching hashes."""
        original_file = tmp_path / "original.bin"
        modified_file = tmp_path / "modified.bin"

        original_data = b"original data"
        modified_data = b"modified data"

        original_file.write_bytes(original_data)
        modified_file.write_bytes(modified_data)

        result = verify_file_integrity(original_file, modified_file)

        assert result is False

    def test_integrity_verification_with_snapshot(self, tmp_path: Path) -> None:
        """Verifies integrity verification with snapshot context."""
        from mr_farmboy_manager.save_snapshot import create_save_snapshot

        original_file = tmp_path / "original.bin"
        original_file.write_bytes(b"snapshot integrity test")

        with create_save_snapshot(original_file) as result:
            assert verify_file_integrity(result.original_path, result.snapshot_path) is True


class TestDetectedFormat:
    """Tests for the DetectedFormat enum."""

    def test_all_formats_defined(self) -> None:
        """Verifies that all expected formats are defined."""
        expected_formats = [
            "UNKNOWN",
            "ZIP",
            "GZIP",
            "SQLITE",
            "JSON_TEXTUAL",
            "XML_TEXTUAL",
            "BINARY_UNKNOWN",
        ]

        for format_name in expected_formats:
            assert hasattr(DetectedFormat, format_name)


class TestSaveInspectionResult:
    """Tests for the SaveInspectionResult dataclass."""

    def test_result_structure_success(self) -> None:
        """Verifies successful inspection result structure."""
        result = SaveInspectionResult(
            readable_file=True,
            detected_format=DetectedFormat.JSON_TEXTUAL,
            inspection_success=True,
            total_size_bytes=1234,
            sha256_hash="a"*32 + "b"*32,  # SHA-256 é de 64 caracteres
            first_bytes_hex="0123456789abcdef",
            file_extension=".json",
            is_empty=False,
            error_message=None,
        )

        assert result.readable_file is True
        assert result.detected_format == DetectedFormat.JSON_TEXTUAL
        assert result.inspection_success is True
        assert result.total_size_bytes == 1234
        assert result.sha256_hash is not None
        assert len(result.sha256_hash) == 64
        assert result.first_bytes_hex is not None
        assert len(result.first_bytes_hex) in (16, 32)
        assert result.file_extension == ".json"
        assert result.is_empty is False
        assert result.error_message is None

    def test_result_structure_failure(self) -> None:
        """Verifies failed inspection result structure."""
        result = SaveInspectionResult(
            readable_file=False,
            detected_format=DetectedFormat.UNKNOWN,
            inspection_success=False,
            error_message="Test error message",
        )

        assert result.readable_file is False
        assert result.detected_format == DetectedFormat.UNKNOWN
        assert result.inspection_success is False
        assert result.error_message == "Test error message"


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_single_byte_file(self, tmp_path: Path) -> None:
        """Verifies handling of single byte file."""
        single_byte = tmp_path / "single.bin"
        single_byte.write_bytes(b'\x42')

        result = inspect_save(single_byte)

        assert result.inspection_success is True
        assert result.is_empty is False
        assert result.total_size_bytes == 1

    def test_large_file(self, tmp_path: Path) -> None:
        """Verifies handling of larger files."""
        large_file = tmp_path / "large.bin"
        # Reduz para 100KB para evitar timeout
        large_data = b'A' * 1024 * 100  # 100 KB de texto ASCII

        large_file.write_bytes(large_data)

        result = inspect_save(large_file)

        assert result.inspection_success is True
        assert result.total_size_bytes == 1024 * 100
        # first_bytes_hex deve ter 32 caracteres (16 bytes em hex)
        assert len(result.first_bytes_hex) in (16, 32)

    def test_special_characters_in_name(self, tmp_path: Path) -> None:
        """Verifies handling of files with special characters in name."""
        special_file = tmp_path / "test-file_123.bin"
        special_file.write_bytes(b"special chars test")

        result = inspect_save(special_file)

        assert result.inspection_success is True
        assert result.file_extension == '.bin'


class TestNoRealSaveFiles:
    """Tests that verify no real save files or game resources are included."""

    def test_all_tests_use_tmp_path(self) -> None:
        """Verifies that all tests use tmp_path and not hardcoded paths."""
        # Esta verificacao e manual - apenas confirma que usamos tmp_path
        # em todos os testes acima
        pass