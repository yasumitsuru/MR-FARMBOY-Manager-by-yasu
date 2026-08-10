from pathlib import Path

import pytest

import mr_farmboy_manager.save_discovery as discovery_module
import mr_farmboy_manager.save_inspector as inspector_module
import mr_farmboy_manager.save_loader as loader_module
from mr_farmboy_manager.save_discovery import SavedFormat, discover_save_structure
from mr_farmboy_manager.save_inspector import inspect_save
from mr_farmboy_manager.save_loader import load_save


PRIVATE_TOKEN = "PRIVATE-C:\\Users\\secret\\save.tres"


def test_loader_sanitizes_unexpected_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save = tmp_path / "save.tres"
    save.write_bytes(b"data")

    def fail_read(*_args, **_kwargs):
        raise ValueError(PRIVATE_TOKEN)

    monkeypatch.setattr(loader_module, "read_limited_file", fail_read)
    result = load_save(save)

    assert not result.success
    assert result.error_message == "O arquivo está vazio ou possui conteúdo inválido."
    assert PRIVATE_TOKEN not in result.error_message
    assert str(tmp_path) not in result.error_message


def test_inspector_does_not_echo_invalid_path(tmp_path: Path) -> None:
    private_path = tmp_path / "private-missing-save.tres"

    result = inspect_save(private_path)

    assert not result.inspection_success
    assert result.error_message == "O caminho não aponta para um arquivo válido."
    assert str(private_path) not in result.error_message


def test_inspector_sanitizes_filesystem_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save = tmp_path / "save.tres"
    save.write_bytes(b"data")

    def fail_read(*_args, **_kwargs):
        raise OSError(PRIVATE_TOKEN)

    monkeypatch.setattr(inspector_module, "read_limited_file", fail_read)
    result = inspect_save(save)

    assert not result.inspection_success
    assert result.error_message == "Não foi possível ler o arquivo."
    assert PRIVATE_TOKEN not in result.error_message


def test_inspector_sanitizes_parsing_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save = tmp_path / "save.tres"
    save.write_bytes(b"data")

    def fail_detection(*_args, **_kwargs):
        raise RuntimeError(PRIVATE_TOKEN)

    monkeypatch.setattr(inspector_module, "_detect_format", fail_detection)
    result = inspect_save(save)

    assert not result.inspection_success
    assert result.error_message == "Não foi possível inspecionar o arquivo."
    assert PRIVATE_TOKEN not in result.error_message


def test_discovery_sanitizes_parser_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save = tmp_path / "save.json"
    save.write_text('{"farm": 1}', encoding="utf-8")

    monkeypatch.setattr(
        discovery_module,
        "_discover_format",
        lambda _data: SavedFormat.JSON_OBJECT,
    )

    def fail_validation(*_args, **_kwargs):
        raise ValueError(PRIVATE_TOKEN)

    monkeypatch.setattr(
        discovery_module,
        "_validate_json_structure",
        fail_validation,
    )
    result = discover_save_structure(save)

    assert not result.success
    assert result.error_message == "Não foi possível analisar a estrutura do arquivo."
    assert PRIVATE_TOKEN not in result.error_message
    assert str(tmp_path) not in result.error_message
