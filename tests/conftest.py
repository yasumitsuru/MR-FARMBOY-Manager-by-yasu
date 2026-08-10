"""Fixtures compartilhadas e protecoes para testes locais."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

# O estilo precisa ser conhecido antes de qualquer import/criação do QApplication.
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtWidgets import QApplication


TEST_SAVE_PATH = Path(
    os.environ.get(
        "MR_FARMBOY_TEST_SAVE_PATH",
        r"C:\Users\maday\AppData\Roaming\Godot\app_userdata\MR FARMBOY\game_data\save_1",
    )
)

TEST_GAME_PATH = Path(
    os.environ.get(
        "MR_FARMBOY_TEST_GAME_PATH",
        r"W:\Games\Steam\steamapps\common\MrFarmBoy",
    )
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Instância Qt compartilhada, sem iniciar o loop de eventos."""
    app = QApplication.instance()
    if app is not None:
        return app
    return QApplication([])


@pytest.fixture(scope="session")
def test_save_path() -> Path:
    """Caminho de save local configuravel, usado apenas como valor de teste."""
    return TEST_SAVE_PATH


@pytest.fixture(scope="session")
def test_game_path() -> Path:
    """Caminho de instalacao local configuravel, usado apenas como valor de teste."""
    return TEST_GAME_PATH


@pytest.fixture(autouse=True)
def prevent_interactive_file_dialogs(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Impede que a suite automatizada aguarde interacao humana."""
    dialog_calls: list[str] = []

    def reject_existing_directory(*_args: object, **_kwargs: object) -> str:
        dialog_calls.append("getExistingDirectory")
        return ""

    def reject_file_dialog(
        *_args: object, **_kwargs: object
    ) -> tuple[str, str]:
        dialog_calls.append("file dialog")
        return "", ""

    def reject_message_box(*_args: object, **_kwargs: object):
        dialog_calls.append("message box")
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        reject_existing_directory,
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", reject_file_dialog)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", reject_file_dialog)
    monkeypatch.setattr(QMessageBox, "warning", reject_message_box)

    yield

    assert dialog_calls == [], (
        "Diálogo Qt real bloqueado: injete um chooser/confirmador ou aplique mock no teste. "
        f"Chamadas: {', '.join(dialog_calls)}"
    )
