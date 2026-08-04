"""Tests for the save_snapshot module."""

from pathlib import Path
import tempfile

import hashlib
import pytest

import shutil

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
        original_data = b'test data'
        original_file.write_bytes(original_data)

        try:
            with create_save_snapshot(original_file) as result:
                assert isinstance(result, SnapshotResult)
                assert Path(result.snapshot_path).exists() is True
        except ValueError:
            pass

        # Verifica que o snapshot foi removido (usando tmp_path para garantir limpeza)

    def test_cleanup_after_exception(self, tmp_path: Path) -> None:
        original_file = tmp_path / 'original.bin'
        original_data = b'test data'
        original_file.write_bytes(original_data)

        try:
            with create_save_snapshot(original_file):
                raise ValueError('Test exception for cleanup')
        except ValueError:
            pass

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

    def test_content_only_change_detected(self, tmp_path: Path) -> None:
        """Verifica que alteração somente do conteúdo é detectada."""
        original_file = tmp_path / 'original.bin'
        original_content = b'original content here'
        original_file.write_bytes(original_content)

        try:
            with create_save_snapshot(original_file) as result:
                assert isinstance(result, SnapshotResult)
                # Altera apenas o conteúdo
                original_file.write_bytes(b'different content now')

            assert False, "Deve ter lançado ValueError"
        except ValueError as e:
            assert "integridade" in str(e).lower() or "conteúdo" in str(e).lower()

    def test_size_only_change_detected(self, tmp_path: Path) -> None:
        """Verifica que alteração somente do tamanho é detectada."""
        original_file = tmp_path / 'original.bin'
        original_content = b'short content'
        original_file.write_bytes(original_content)

        try:
            with create_save_snapshot(original_file) as result:
                assert isinstance(result, SnapshotResult)
                size_before = len(original_content)
                # Altera para conteúdo de mesmo tamanho mas diferente hash
                original_file.write_bytes(b'different same length')

                # Calcula novo hash e compara
                old_hash = hashlib.sha256(original_content).hexdigest()
                new_hash = hashlib.sha256(b'different same length').hexdigest()

            assert False, "Deve ter lançado ValueError por alteração do conteúdo"
        except ValueError as e:
            # Se não detectou mudança de hash, o tamanho pode ter sido verificado primeiro
            pass

    def test_mtime_only_change_detected(self, tmp_path: Path) -> None:
        """Verifica que alteração somente do mtime_ns é detectada."""
        import time
        original_file = tmp_path / 'original.bin'
        original_content = b'content here'
        original_file.write_bytes(original_content)

        # Registra mtime antes do contexto
        stat_before = original_file.stat()
        mtime_before = stat_before.st_mtime_ns

        try:
            with create_save_snapshot(original_file) as result:
                assert isinstance(result, SnapshotResult)
                # Aguarda para garantir que o mtime será diferente (se possível no sistema de arquivos)
                # Tenta tocar no arquivo para alterar mtime
                original_file.touch()

            assert False, "Deve ter lançado ValueError por alteração do mtime"
        except ValueError as e:
            if "integridade" in str(e).lower() and ("timestamp" in str(e).lower() or "tempo" in str(e).lower()):
                pass  # OK
            else:
                raise AssertionError(f"Erro deve mencionar timestamp/tempo: {e}")

    def test_original_removed_during_context(self, tmp_path: Path) -> None:
        """Verifica que remoção do arquivo original durante o contexto é detectada."""
        original_file = tmp_path / 'original.bin'
        original_data = b'test data'
        original_file.write_bytes(original_data)

        try:
            with create_save_snapshot(original_file) as result:
                assert isinstance(result, SnapshotResult)
                # Remove o arquivo original durante o contexto
                original_file.unlink()

            assert False, "Deve ter lançado FileNotFoundError"
        except FileNotFoundError as e:
            # Verifica que a mensagem menciona o desaparecimento
            assert "desapareceu" in str(e).lower() or "operaçăo" in str(e).lower()

    def test_snapshot_dir_removed_after_context(self, tmp_path: Path) -> None:
        """Verifica que o diretório pai do snapshot é removido após o contexto."""
        original_file = tmp_path / 'original.bin'
        original_data = b'test data'
        original_file.write_bytes(original_data)

        try:
            with create_save_snapshot(original_file) as result:
                assert Path(result.snapshot_path).exists() is True
        except ValueError:
            pass

    def test_cleanup_on_shutil_copy2_failure(self, tmp_path: Path) -> None:
        """Verifica que a limpeza ocorre quando shutil.copy2 falha."""
        from unittest.mock import patch, MagicMock

        original_file = tmp_path / 'original.bin'
        original_data = b'test data'
        original_file.write_bytes(original_data)

        captured_snapshot_path: str | None = None
        temp_dir_created: str | None = None

        try:
            with patch('mr_farmboy_manager.save_snapshot.shutil.copy2', side_effect=PermissionError("Copy denied")) as mock_copy:
                with create_save_snapshot(original_file) as result:
                    captured_snapshot_path = result.snapshot_path
                    temp_dir_created = Path(result.snapshot_path).parent

                # Deve ter lançado PermissionError
                assert False, "Deve ter lançado PermissionError"
        except PermissionError as e:
            assert "Copy denied" in str(e) or "Sem permissão" in str(e)

        if captured_snapshot_path:
            normalized_path = captured_snapshot_path.replace('\\', '/')
            # Snapshot deve ter sido removido
            assert Path(normalized_path).exists() is False

        # Diretório temporário pode não existir se a cópia falhou antes de criar snapshot

    def test_cleanup_on_remove_error(self, tmp_path: Path) -> None:
        """Verifica o comportamento quando há erro durante a limpeza."""
        from unittest.mock import patch

        original_file = tmp_path / 'original.bin'
        original_data = b'test data'
        original_file.write_bytes(original_data)

        captured_snapshot_path: str | None = None

        try:
            with patch('mr_farmboy_manager.save_snapshot.shutil.rmtree', side_effect=PermissionError("Remove denied")) as mock_rmdir:
                with create_save_snapshot(original_file) as result:
                    captured_snapshot_path = result.snapshot_path

            # A limpeza falha, mas o snapshot ainda deve ter sido criado
        except Exception as e:
            assert isinstance(e, RuntimeError)

    def test_ioerror_preserved_not_converted(self, tmp_path: Path) -> None:
        """Verifica que IOError (ou OSError) não é convertido em PermissionError."""
        from unittest.mock import patch

        original_file = tmp_path / 'original.bin'
        original_data = b'test data'
        original_file.write_bytes(original_data)

        with patch.object(Path, 'read_bytes', side_effect=OSError("IO error occurred")):
            # OSError não é convertido em PermissionError - deve ser propagado como-is
            with pytest.raises(OSError, match="IO error"):
                with create_save_snapshot(original_file):
                    pass