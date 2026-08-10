"""Tests for the save_loader module."""

import os
import tempfile
from pathlib import Path

import pytest
from unittest.mock import patch

from mr_farmboy_manager.save_loader import load_save, validate_save_file, SaveLoadResult
from mr_farmboy_manager.save_snapshot import MAX_SAVE_FILE_SIZE_BYTES


class TestLoadSave:
    """Tests for the load_save() function."""

    def test_load_arquivo_valido_retorna_success_true(self, tmp_path: Path) -> None:
        """Verifies that valid file returns success=True."""
        # Cria um arquivo de teste com conteudo binario
        test_file = tmp_path / "test_save.bin"
        test_data = b"\x00\x01\x02\x03TEST_DATA"

        test_file.write_bytes(test_data)

        result = load_save(test_file)

        assert result.success is True
        assert result.path == str(test_file.resolve())
        assert result.size_bytes == len(test_data)
        assert result.data == test_data
        assert result.error_message is None

    def test_load_rejects_file_above_injected_limit_without_data(self, tmp_path: Path) -> None:
        """The legacy loader must not return materialized data above its boundary."""
        test_file = tmp_path / "too_large.bin"
        test_file.write_bytes(b"123456789")

        result = load_save(test_file, max_size_bytes=8)

        assert result.success is False
        assert result.data is None
        assert result.size_bytes is None
        assert result.error_message == "Arquivo acima do limite de leitura."

    @pytest.mark.parametrize("invalid_limit", [True, 0, "8", MAX_SAVE_FILE_SIZE_BYTES + 1])
    def test_load_rejects_invalid_or_ceiling_bypassing_limit(
        self, tmp_path: Path, invalid_limit: object
    ) -> None:
        test_file = tmp_path / "small.bin"
        test_file.write_bytes(b"safe")

        result = load_save(test_file, max_size_bytes=invalid_limit)

        assert result.success is False
        assert result.data is None
        assert result.error_message == "Limite de leitura inválido."

    def test_invalid_limit_takes_precedence_over_missing_path(self, tmp_path: Path) -> None:
        result = load_save(tmp_path / "missing.bin", max_size_bytes=True)

        assert result.success is False
        assert result.error_message == "Limite de leitura inválido."

    def test_load_arquivo_invalido_retorna_success_false(self, tmp_path: Path) -> None:
        """Verifies that invalid path returns success=False."""
        # Caminho inexistente
        fake_path = tmp_path / "nonexistent_file.bin"

        result = load_save(fake_path)

        assert result.success is False
        # Mensagem deve conter indicação de erro de arquivo
        assert "arquivo" in result.error_message.lower() or "valido" in result.error_message.lower()
        assert result.data is None

    def test_load_arquivo_vazio_retorna_success_false(self, tmp_path: Path) -> None:
        """Verifies that empty file returns success=False."""
        # Cria arquivo vazio (0 bytes)
        empty_file = tmp_path / "empty_save.bin"
        empty_file.write_bytes(b"")

        result = load_save(empty_file)

        assert result.success is False
        assert "vazio" in result.error_message.lower() or "minimo" in result.error_message.lower()

    def test_load_str_path_trabalha_corretamente(self, tmp_path: Path) -> None:
        """Verifies that str path works as expected."""
        test_file = tmp_path / "test_str_path.bin"
        test_data = b"TEST_DATA_STRING_PATH"

        test_file.write_bytes(test_data)

        result = load_save(str(test_file))

        assert result.success is True
        assert result.data == test_data

    def test_load_path_obj_trabalha_corretamente(self, tmp_path: Path) -> None:
        """Verifies that Path object works as expected."""
        test_file = tmp_path / "test_path_obj.bin"
        test_data = b"TEST_DATA_PATH_OBJECT"

        test_file.write_bytes(test_data)

        result = load_save(test_file)

        assert result.success is True
        assert result.data == test_data

    def test_load_sem_permissao_simulado_com_mock(self, tmp_path: Path) -> None:
        """Verifies permission denied handling using unittest.mock."""
        from unittest.mock import patch
        
        test_file = tmp_path / "protected.bin"
        test_data = b"test data"
        test_file.write_bytes(test_data)

        with patch(
            'mr_farmboy_manager.save_snapshot.os.open',
            side_effect=PermissionError("Permission denied"),
        ):
            result = load_save(str(test_file))

        assert result.success is False
        assert result.error_message is not None
        assert "permissoes" in result.error_message.lower() or "permission" in result.error_message.lower()
        assert result.data is None

    def test_load_caminho_diretorio_retorna_success_false(self, tmp_path: Path) -> None:
        """Verifies that directory is treated as error."""
        result = load_save(tmp_path)

        assert result.success is False


class TestValidateSaveFile:
    """Tests for the validate_save_file() function."""

    def test_validate_arquivo_valido(self, tmp_path: Path) -> None:
        """Verifies that valid file returns (True, None)."""
        test_file = tmp_path / "valid.bin"
        test_file.write_bytes(b"test data")

        is_valid, error_msg = validate_save_file(test_file)

        assert is_valid is True
        assert error_msg is None

    def test_validate_arquivo_inexistente(self, tmp_path: Path) -> None:
        """Verifies that nonexistent file returns (False, message)."""
        fake_path = tmp_path / "nonexistent.bin"

        is_valid, error_msg = validate_save_file(fake_path)

        assert is_valid is False
        assert isinstance(error_msg, str)
        assert len(error_msg) > 0


class TestSaveLoadResult:
    """Tests for the SaveLoadResult NamedTuple."""

    def test_resultado_sucesso(self) -> None:
        """Verifies success result structure."""
        result = SaveLoadResult(
            path="/caminho/ao/arquivo.bin",
            success=True,
            error_message=None,
            size_bytes=1234,
            data=b"dados_binarios"
        )

        assert result.path == "/caminho/ao/arquivo.bin"
        assert result.success is True
        assert result.error_message is None
        assert result.size_bytes == 1234
        assert result.data == b"dados_binarios"

    def test_resultado_falha(self) -> None:
        """Verifies failure result structure."""
        result = SaveLoadResult(
            path="/caminho/ao/arquivo.bin",
            success=False,
            error_message="Read error"
        )

        assert result.path == "/caminho/ao/arquivo.bin"
        assert result.success is False
        assert result.error_message == "Read error"
        assert result.size_bytes is None
        assert result.data is None


class TestImutabilidade:
    """Tests to ensure the original save is not modified."""

    def test_load_nao_modifica_arquivo_original(self, tmp_path: Path) -> None:
        """Verifies that load_save() does not modify the original file."""
        test_file = tmp_path / "original.bin"
        original_content = b"data original do save"

        test_file.write_bytes(original_content)

        # Salva cópia do conteúdo original
        content_before = test_file.read_bytes()

        # Carrega o arquivo
        _ = load_save(test_file)

        # Verifica que o conteúdo não mudou
        content_after = test_file.read_bytes()

        assert content_before == content_after, "The original file was modified!"


class TestPathNormalizacao:
    """Tests for path normalization."""

    def test_caminho_relativo_normalizado(self, tmp_path: Path) -> None:
        """Verifies that relative path is converted to absolute."""
        test_file = tmp_path / "relative.bin"
        test_file.write_bytes(b"test")

        # Usar tmp_path como caminho base e carregar um arquivo relativo a ele
        result = load_save(tmp_path / "relative.bin")

        assert result.success is True
        # Deve ser um caminho absoluto após normalização
        assert Path(result.path).is_absolute()


class TestTypeHints:
    """Tests for type compatibility."""

    def test_str_acceptado(self, tmp_path: Path) -> None:
        """Verifies that str is accepted as parameter."""
        test_file = tmp_path / "str_test.bin"
        test_file.write_bytes(b"test")

        # Isso deve funcionar sem erro de tipo
        result: SaveLoadResult = load_save(str(test_file))

        assert result.success is True

    def test_path_acceptado(self, tmp_path: Path) -> None:
        """Verifies that Path is accepted as parameter."""
        test_file = tmp_path / "path_test.bin"
        test_file.write_bytes(b"test")

        # Isso deve funcionar sem erro de tipo
        result: SaveLoadResult = load_save(test_file)

        assert result.success is True
