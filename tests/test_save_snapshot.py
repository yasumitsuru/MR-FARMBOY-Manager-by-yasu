"""Tests for the save_snapshot module."""

from pathlib import Path

import pytest

from mr_farmboy_manager.save_snapshot import (
    create_save_snapshot,
    SnapshotResult,
)


class TestCreateSaveSnapshot:
    """Tests for the create_save_snapshot context manager."""

    def test_snapshot_created_at_different_path(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'test data')
        with create_save_snapshot(original_file) as result:
            assert isinstance(result, SnapshotResult)
            assert result.snapshot_path != str(original_file)

    def test_content_identical_to_original(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_data = b'test content'
        original_file.write_bytes(original_data)
        with create_save_snapshot(original_file) as result:
            assert result.size_bytes == len(original_data)

    def test_sha256_identical(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'sha256 data')
        with create_save_snapshot(original_file) as result:
            assert result.original_sha256 == result.snapshot_sha256

    def test_hash_format(self, tmp_path: Path) -> None:
        """Verifies that SHA-256 hashes are 64 hex characters."""
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'hash format')
        with create_save_snapshot(original_file) as result:
            assert len(result.original_sha256) == 64
            assert len(result.snapshot_sha256) == 64
            assert all(c in '0123456789abcdef' for c in result.original_sha256)

    def test_original_not_modified(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_content = b'original data'
        original_file.write_bytes(original_content)
        content_before = original_file.read_bytes()
        with create_save_snapshot(original_file):
            pass
        content_after = original_file.read_bytes()
        assert content_before == content_after

    def test_snapshot_removed_on_context_exit(self, tmp_path: Path) -> None:
        """Verifies snapshot is cleaned up after context manager exits."""
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'cleanup')
        with create_save_snapshot(original_file):
            pass
        # Verifica que não há diretórios temporários restantes
        remaining = list(tmp_path.glob('**/*mr_farmboy_snapshot*'))
        assert len(remaining) == 0

    def test_cleanup_after_exception(self, tmp_path: Path) -> None:
        """Verifies snapshot is cleaned up even when exception occurs."""
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'excepcion')
        try:
            with create_save_snapshot(original_file):
                raise ValueError('test')
        except ValueError:
            pass
        remaining = list(tmp_path.glob('**/*mr_farmboy_snapshot*'))
        assert len(remaining) == 0

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies FileNotFoundError for nonexistent files."""
        with pytest.raises(FileNotFoundError):
            with create_save_snapshot(tmp_path / 'nonexistent.bin'):
                pass

    def test_directory_path_raises(self, tmp_path: Path) -> None:
        """Verifies that a directory path raises an error."""
        with pytest.raises(FileNotFoundError):
            with create_save_snapshot(tmp_path):
                pass

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        """Verifies that empty file raises ValueError."""
        original = tmp_path / 'empty.bin'
        original.write_bytes(b'')
        with pytest.raises(ValueError, match='Arquivo vazio'):
            with create_save_snapshot(original):
                pass

    def test_permission_error_mocked(self, tmp_path: Path) -> None:
        """Verifies PermissionError is handled properly."""
        from unittest.mock import patch
        
        original_file = tmp_path / 'protected.bin'
        original_file.write_bytes(b'permission')
        
        # Mocka open para retornar PermissionError
        with patch('builtins.open', side_effect=PermissionError('denied')):
            with pytest.raises(PermissionError):
                with create_save_snapshot(original_file):
                    pass


class TestSnapshotResult:
    """Tests for SnapshotResult dataclass."""

    def test_result_structure(self) -> None:
        result = SnapshotResult(
            original_path='/path/original.bin',
            snapshot_path='/path/snapshot.bin',
            size_bytes=123,
            original_sha256='abc' * 16,
            snapshot_sha256='abc' * 16,
        )
        assert result.size_bytes == 123
        assert result.original_path == '/path/original.bin'
        assert result.snapshot_path == '/path/snapshot.bin'


class TestHashVerification:
    """Tests for hash verification."""

    def test_hash_verification_success(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'hash test')
        with create_save_snapshot(original_file) as result:
            assert result.original_sha256 == result.snapshot_sha256

    def test_original_integrity_preserved(self, tmp_path: Path) -> None:
        """Verifies hash before and after copy are identical."""
        original_file = tmp_path / 'original.bin'
        original_data = b'integrity data'
        original_file.write_bytes(original_data)
        
        with create_save_snapshot(original_file) as result:
            assert result.original_sha256 == result.snapshot_sha256


class TestEdgeCases:
    """Tests for edge cases."""

    def test_binary_data(self, tmp_path: Path) -> None:
        """Verifies handling of binary data with null bytes."""
        original_file = tmp_path / 'binary.bin'
        original_file.write_bytes(b'\x00\x01\x02\xff\xfe')
        with create_save_snapshot(original_file) as result:
            assert result.size_bytes == 5

    def test_large_file(self, tmp_path: Path) -> None:
        """Verifies handling of larger files (1 MB)."""
        original_file = tmp_path / 'large.bin'
        large_data = b'x' * (1024 * 1024)
        original_file.write_bytes(large_data)
        with create_save_snapshot(original_file) as result:
            assert result.size_bytes == 1024 * 1024

    def test_special_characters_in_name(self, tmp_path: Path) -> None:
        """Verifies files with special characters in name."""
        original_file = tmp_path / 'test-save_1.bin'
        original_data = b'special chars'
        original_file.write_bytes(original_data)
        with create_save_snapshot(original_file) as result:
            assert result.size_bytes == len(original_data)
