"""Tests for the save_snapshot module."""

from pathlib import Path

import hashlib
import pytest

from mr_farmboy_manager.save_snapshot import (
    create_save_snapshot,
    SnapshotResult,
)


class TestCreateSaveSnapshot:
    """Tests for the create_save_snapshot context manager."""

    def test_snapshot_created_at_different_path(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_data = b'test data'
        original_file.write_bytes(original_data)

        with create_save_snapshot(original_file) as result:
            assert isinstance(result, SnapshotResult)
            assert not str(result.snapshot_path).startswith(str(tmp_path))

    def test_content_identical_to_original(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_data = b'test content with specific data'
        original_file.write_bytes(original_data)

        with create_save_snapshot(original_file) as result:
            snapshot_bytes = Path(result.snapshot_path).read_bytes()
            assert snapshot_bytes == original_data

    def test_size_identical_to_original(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_data = b'test content for size check'
        original_file.write_bytes(original_data)

        with create_save_snapshot(original_file) as result:
            assert result.size_bytes == len(original_data)

    def test_sha256_identical(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_data = b'sha256 data for verification'
        original_file.write_bytes(original_data)

        with create_save_snapshot(original_file) as result:
            assert result.original_sha256 == result.snapshot_sha256

    def test_hash_format_is_64_hex_chars(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'hash format test')

        with create_save_snapshot(original_file) as result:
            assert len(result.original_sha256) == 64
            assert len(result.snapshot_sha256) == 64

    def test_original_not_modified(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_content = b'original data content'
        original_file.write_bytes(original_content)

        content_before = original_file.read_bytes()
        stat_before = original_file.stat()
        size_before = len(content_before)
        mtime_ns_before = stat_before.st_mtime_ns

        with create_save_snapshot(original_file) as result:
            assert isinstance(result, SnapshotResult)

            content_during = original_file.read_bytes()
            stat_during = original_file.stat()

            assert content_during == content_before
            assert size_before == len(content_during)
            assert mtime_ns_before == stat_during.st_mtime_ns

    def test_snapshot_removed_after_context(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'test data')

        captured_snapshot_path: str | None = None

        try:
            with create_save_snapshot(original_file) as result:
                assert isinstance(result, SnapshotResult)
                captured_snapshot_path = result.snapshot_path
                assert Path(captured_snapshot_path).exists() is True

            if captured_snapshot_path is not None:
                assert Path(captured_snapshot_path).exists() is False
        except ValueError:
            pass

        if captured_snapshot_path is not None:
            assert Path(captured_snapshot_path).exists() is False

    def test_cleanup_after_exception(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_file.write_bytes(b'test data')

        captured_snapshot_path: str | None = None

        try:
            with create_save_snapshot(original_file) as result:
                captured_snapshot_path = result.snapshot_path
                raise ValueError('Test exception for cleanup')
        except ValueError:
            pass

        if captured_snapshot_path is not None:
            assert Path(captured_snapshot_path).exists() is False

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="não aponta para um arquivo válido"):
            with create_save_snapshot(tmp_path / 'nonexistent.bin'):
                pass

    def test_directory_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="não aponta para um arquivo"):
            with create_save_snapshot(tmp_path):
                pass

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        original = tmp_path / 'empty.bin'
        original.write_bytes(b'')

        with pytest.raises(ValueError, match="Arquivo vazio"):
            with create_save_snapshot(original):
                pass

    def test_permission_error_mocked(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        original_file = tmp_path / 'protected.bin'
        original_file.write_bytes(b'test data')

        with patch.object(Path, 'read_bytes', side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError, match="Sem permissão"):
                with create_save_snapshot(original_file):
                    pass

    def test_integrity_check_original_not_modified_after_context(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_content = b'original data for integrity check'
        original_file.write_bytes(original_content)

        try:
            with create_save_snapshot(original_file) as result:
                assert isinstance(result, SnapshotResult)
                original_file.write_bytes(b'modified during snapshot')

            assert False, "Deve ter lançado ValueError"
        except ValueError as e:
            if "integridade" not in str(e).lower():
                raise AssertionError(f"Erro deve mencionar integridade: {e}")

    def test_snapshot_sha256_matches_original(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_data = b'snapshot verification data'
        original_file.write_bytes(original_data)

        with create_save_snapshot(original_file) as result:
            assert isinstance(result, SnapshotResult)
            calculated_hash = hashlib.sha256(original_data).hexdigest()
            assert result.snapshot_sha256 == calculated_hash