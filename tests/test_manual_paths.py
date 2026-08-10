"""Testes para o módulo manual_paths - Backend de apontamento manual."""

from pathlib import Path

import pytest

from mr_farmboy_manager.manual_paths import (
    DirectoryValidationCode,
    DirectoryValidationResult,
    SaveSlotsLoadResult,
    build_save_slot_summaries,
    load_save_slot_summaries,
    validate_directory_path,
)


@pytest.fixture
def tmp_path():
    """Fixture para criar diretórios temporários."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


class TestDirectoryValidationCode:
    """Testes do enum DirectoryValidationCode."""

    def test_valid_code(self):
        """Código VALID existe."""
        assert DirectoryValidationCode.VALID == "valid"

    def test_empty_code(self):
        """Código EMPTY existe."""
        assert DirectoryValidationCode.EMPTY == "empty"

    def test_not_found_code(self):
        """Código NOT_FOUND existe."""
        assert DirectoryValidationCode.NOT_FOUND == "not_found"

    def test_not_directory_code(self):
        """Código NOT_DIRECTORY existe."""
        assert DirectoryValidationCode.NOT_DIRECTORY == "not_directory"


class TestDirectoryValidationResult:
    """Testes da dataclass DirectoryValidationResult."""

    def test_result_is_frozen(self):
        """Teste que DirectoryValidationResult é imutável."""
        result = DirectoryValidationResult(
            code=DirectoryValidationCode.VALID,
            path=Path("/valid/path"),
        )

        with pytest.raises(AttributeError):
            result.code = DirectoryValidationCode.EMPTY

    def test_is_valid_true_for_valid(self):
        """is_valid é True para VALID."""
        result = DirectoryValidationResult(
            code=DirectoryValidationCode.VALID,
            path=Path("/valid/path"),
        )
        assert result.is_valid is True

    def test_is_valid_false_for_empty(self):
        """is_valid é False para EMPTY."""
        result = DirectoryValidationResult(
            code=DirectoryValidationCode.EMPTY,
            path=None,
        )
        assert result.is_valid is False

    def test_is_valid_false_for_not_found(self):
        """is_valid é False para NOT_FOUND."""
        result = DirectoryValidationResult(
            code=DirectoryValidationCode.NOT_FOUND,
            path=Path("/nonexistent"),
        )
        assert result.is_valid is False

    def test_is_valid_false_for_not_directory(self):
        """is_valid é False para NOT_DIRECTORY."""
        result = DirectoryValidationResult(
            code=DirectoryValidationCode.NOT_DIRECTORY,
            path=Path("/not/a/dir"),
        )
        assert result.is_valid is False

    def test_path_none_for_empty(self):
        """path é None para EMPTY."""
        result = DirectoryValidationResult(
            code=DirectoryValidationCode.EMPTY,
            path=None,
        )
        assert result.path is None

    def test_path_set_for_non_empty(self):
        """path contém valor normalizado para códigos não vazios."""
        result = DirectoryValidationResult(
            code=DirectoryValidationCode.NOT_FOUND,
            path=Path("/some/path"),
        )
        assert result.path is not None


class TestValidateDirectoryPath:
    """Testes da função validate_directory_path."""

    def test_none_returns_empty(self):
        """None retorna EMPTY."""
        result = validate_directory_path(None)
        assert result.code == DirectoryValidationCode.EMPTY
        assert result.path is None

    def test_empty_string_returns_empty(self):
        """String vazia retorna EMPTY."""
        result = validate_directory_path("")
        assert result.code == DirectoryValidationCode.EMPTY
        assert result.path is None

    def test_whitespace_string_returns_empty(self):
        """String apenas com espaços retorna EMPTY."""
        result = validate_directory_path("   ")
        assert result.code == DirectoryValidationCode.EMPTY
        assert result.path is None

    def test_nonexistent_path_returns_not_found(self, tmp_path):
        """Caminho inexistente retorna NOT_FOUND."""
        nonexistent = tmp_path / "nonexistent_dir"
        result = validate_directory_path(nonexistent)
        assert result.code == DirectoryValidationCode.NOT_FOUND
        assert result.path is not None

    def test_file_returns_not_directory(self, tmp_path):
        """Arquivo existente retorna NOT_DIRECTORY."""
        file_path = tmp_path / "test_file.txt"
        file_path.touch()
        result = validate_directory_path(file_path)
        assert result.code == DirectoryValidationCode.NOT_DIRECTORY
        assert result.path is not None

    def test_existing_directory_returns_valid(self, tmp_path):
        """Diretório existente retorna VALID."""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        result = validate_directory_path(dir_path)
        assert result.code == DirectoryValidationCode.VALID
        assert result.path is not None

    def test_string_path_converted_to_path(self, tmp_path):
        """Caminho em string é convertido para Path."""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        str_path = str(dir_path)
        result = validate_directory_path(str_path)
        assert isinstance(result.path, Path)

    def test_is_valid_true_only_for_valid(self, tmp_path):
        """is_valid é verdadeiro somente para VALID."""
        # VALID
        dir_path = tmp_path / "valid_dir"
        dir_path.mkdir()
        valid_result = validate_directory_path(dir_path)
        assert valid_result.is_valid is True

        # EMPTY
        empty_result = validate_directory_path(None)
        assert empty_result.is_valid is False

        # NOT_FOUND
        not_found_result = validate_directory_path(tmp_path / "nonexistent")
        assert not_found_result.is_valid is False

        # NOT_DIRECTORY
        file_path = tmp_path / "file.txt"
        file_path.touch()
        not_dir_result = validate_directory_path(file_path)
        assert not_dir_result.is_valid is False


class TestSaveSlotsLoadResult:
    """Testes da dataclass SaveSlotsLoadResult."""

    def test_result_is_frozen(self):
        """Teste que SaveSlotsLoadResult é imutável."""
        validation = DirectoryValidationResult(
            code=DirectoryValidationCode.VALID,
            path=Path("/valid"),
        )
        result = SaveSlotsLoadResult(validation=validation, summaries=())

        with pytest.raises(AttributeError):
            result.validation = DirectoryValidationResult(
                code=DirectoryValidationCode.EMPTY,
                path=None,
            )

    def test_is_success_true_for_valid(self):
        """is_success é True quando validação é válida."""
        validation = DirectoryValidationResult(
            code=DirectoryValidationCode.VALID,
            path=Path("/valid"),
        )
        result = SaveSlotsLoadResult(validation=validation, summaries=())
        assert result.is_success is True

    def test_is_success_false_for_invalid(self):
        """is_success é False para validação inválida."""
        validation = DirectoryValidationResult(
            code=DirectoryValidationCode.NOT_FOUND,
            path=Path("/nonexistent"),
        )
        result = SaveSlotsLoadResult(validation=validation, summaries=())
        assert result.is_success is False

    def test_empty_directory_is_success(self, tmp_path):
        """Diretório válido sem slots retorna sucesso e tupla vazia."""
        dir_path = tmp_path / "empty_dir"
        dir_path.mkdir()
        validation = validate_directory_path(dir_path)
        result = load_save_slot_summaries(str(dir_path))
        assert result.is_success is True
        assert result.summaries == ()


class TestLoadSaveSlotSummaries:
    """Testes da função load_save_slot_summaries."""

    def test_load_normalizes_recognized_slot_to_game_data(self, tmp_path: Path) -> None:
        """Selecionar um slot reconhecido carrega os saves a partir de sua raiz."""
        root = tmp_path / "game_data"
        slot = root / "save_1"
        slot.mkdir(parents=True)
        (slot / "crop.tres").write_text("[gd_resource]", encoding="utf-8")

        result = load_save_slot_summaries(slot)

        assert result.validation.code is DirectoryValidationCode.NORMALIZED
        assert result.validation.path == root
        assert [item.slot.number for item in result.summaries] == [1]

    def test_empty_existing_root_remains_valid_and_empty(self, tmp_path: Path) -> None:
        """Uma raiz existente sem slots continua válida e retorna lista vazia."""
        root = tmp_path / "game_data"
        root.mkdir()

        result = load_save_slot_summaries(root)

        assert result.validation.code is DirectoryValidationCode.VALID
        assert result.summaries == ()

    def test_non_slot_directory_never_walks_to_parent(self, tmp_path: Path) -> None:
        """Diretórios fora do padrão de slot nunca são normalizados ao pai."""
        selected = tmp_path / "custom"
        selected.mkdir()
        (tmp_path / "save_2").mkdir()

        result = load_save_slot_summaries(selected)

        assert result.validation.path == selected
        assert result.validation.code is DirectoryValidationCode.VALID

    def test_empty_path_does_not_call_build(self, tmp_path, monkeypatch):
        """Caminho vazio não chama build_save_slot_summaries."""
        called = []

        def mock_build(*args, **kwargs):
            called.append(True)
            return []

        monkeypatch.setattr(
            "mr_farmboy_manager.manual_paths.build_save_slot_summaries",
            mock_build,
        )

        result = load_save_slot_summaries(None)
        assert len(called) == 0
        assert result.validation.code == DirectoryValidationCode.EMPTY

    def test_nonexistent_path_does_not_call_build(self, tmp_path, monkeypatch):
        """Caminho inexistente não chama build_save_slot_summaries."""
        called = []

        def mock_build(*args, **kwargs):
            called.append(True)
            return []

        monkeypatch.setattr(
            "mr_farmboy_manager.manual_paths.build_save_slot_summaries",
            mock_build,
        )

        result = load_save_slot_summaries(tmp_path / "nonexistent")
        assert len(called) == 0
        assert result.validation.code == DirectoryValidationCode.NOT_FOUND

    def test_file_does_not_call_build(self, tmp_path, monkeypatch):
        """Arquivo não chama build_save_slot_summaries."""
        called = []

        def mock_build(*args, **kwargs):
            called.append(True)
            return []

        monkeypatch.setattr(
            "mr_farmboy_manager.manual_paths.build_save_slot_summaries",
            mock_build,
        )

        file_path = tmp_path / "file.txt"
        file_path.touch()
        result = load_save_slot_summaries(file_path)
        assert len(called) == 0
        assert result.validation.code == DirectoryValidationCode.NOT_DIRECTORY

    def test_valid_directory_calls_build_once(self, tmp_path, monkeypatch):
        """Diretório válido chama build_save_slot_summaries uma vez."""
        called_count = []

        def mock_build(base_path):
            called_count.append(base_path)
            return []

        monkeypatch.setattr(
            "mr_farmboy_manager.manual_paths.build_save_slot_summaries",
            mock_build,
        )

        dir_path = tmp_path / "valid_dir"
        dir_path.mkdir()
        result = load_save_slot_summaries(dir_path)
        assert len(called_count) == 1
        assert called_count[0] == dir_path

    def test_valid_directory_passed_as_base_path(self, tmp_path, monkeypatch):
        """O diretório validado é passado como base_path."""
        passed_paths = []

        def mock_build(base_path):
            passed_paths.append(base_path)
            return []

        monkeypatch.setattr(
            "mr_farmboy_manager.manual_paths.build_save_slot_summaries",
            mock_build,
        )

        dir_path = tmp_path / "valid_dir"
        dir_path.mkdir()
        result = load_save_slot_summaries(dir_path)
        assert len(passed_paths) == 1
        assert passed_paths[0] == dir_path

    def test_valid_directory_without_slots_returns_success(self, tmp_path, monkeypatch):
        """Diretório válido sem slots retorna sucesso e tupla vazia."""
        def mock_build(base_path):
            return []

        monkeypatch.setattr(
            "mr_farmboy_manager.manual_paths.build_save_slot_summaries",
            mock_build,
        )

        dir_path = tmp_path / "empty_dir"
        dir_path.mkdir()
        result = load_save_slot_summaries(dir_path)
        assert result.is_success is True
        assert result.summaries == ()

    def test_summaries_preserve_order(self, tmp_path):
        """Resumos mantêm a ordem recebida."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        (game_data_dir / "save_1").mkdir()
        (game_data_dir / "save_2").mkdir()
        (game_data_dir / "save_3").mkdir()

        result = load_save_slot_summaries(game_data_dir)
        assert len(result.summaries) == 3
        assert result.summaries[0].slot.number == 1
        assert result.summaries[1].slot.number == 2
        assert result.summaries[2].slot.number == 3

    def test_same_slot_summary_objects_preserved(self, tmp_path):
        """Os mesmos objetos SaveSlotSummary são preservados."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        (game_data_dir / "save_5").mkdir()
        (game_data_dir / "save_5" / "test.tres").touch()

        result = load_save_slot_summaries(game_data_dir)
        summary = result.summaries[0]
        assert summary is not None
        assert summary.slot.number == 5
        assert summary.tres_file_count == 1

    def test_result_is_immutable(self):
        """SaveSlotsLoadResult é imutável."""
        validation = DirectoryValidationResult(
            code=DirectoryValidationCode.VALID,
            path=Path("/valid"),
        )
        result = SaveSlotsLoadResult(validation=validation, summaries=())

        with pytest.raises(AttributeError):
            result.summaries = ("a", "b")
