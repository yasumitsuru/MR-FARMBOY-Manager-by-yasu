"""Contratos observáveis das páginas QML de configurações e diagnósticos."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Property, QMetaObject, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlComponent, QQmlEngine

from mr_farmboy_manager.presentation.diagnostics_view_model import DiagnosticsViewModel


class _DiagnosticsController(QObject):
    def __init__(self, diagnostics: DiagnosticsViewModel) -> None:
        super().__init__()
        self._diagnostics = diagnostics

    diagnostics = Property(QObject, lambda self: self._diagnostics, constant=True)


def _find(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, f"Ponto estável ausente: {name}"
    return found


def _show(root: QObject, index: int) -> None:
    _find(root, "appShell").setProperty("currentIndex", index)


def _click(item: QObject) -> None:
    assert QMetaObject.invokeMethod(item, "click", Qt.ConnectionType.DirectConnection)


def _create_narrow_page(controller: QObject, page_name: str) -> tuple[QQmlEngine, QObject]:
    """Instancia a página fora da janela principal e de sua largura mínima."""
    from mr_farmboy_manager import _qml_resources  # noqa: F401

    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl(f"qrc:/qml/pages/{page_name}.qml"))
    assert component.isReady(), [str(error) for error in component.errors()]
    page = component.createWithInitialProperties({"controller": controller})
    assert page is not None, [str(error) for error in component.errors()]
    page.setParent(engine)
    page.setWidth(360)
    page.setHeight(640)
    return engine, page


def test_normalized_path_feedback_is_visible(qapp, qml_shell, fake_controller) -> None:
    _show(qml_shell, 3)
    fake_controller.settings.set_fixture_save_root(
        "C:/game_data", "Raiz normalizada para game_data."
    )
    qapp.processEvents()

    assert _find(qml_shell, "saveRootField").property("text") == "C:/game_data"
    assert "normalizada" in _find(qml_shell, "saveRootMessage").property("text").lower()


@pytest.mark.parametrize(
    ("save_state", "game_state", "expected_save", "expected_game"),
    [
        ("valid", "valid", "Válido", "Válido"),
        ("not_found", "not_directory", "Inválido", "Inválido"),
        ("empty", "empty", "Não definido", "Não definido"),
    ],
)
def test_path_badges_cover_valid_invalid_and_unset_states(
    qapp, qml_shell, fake_controller, save_state, game_state, expected_save, expected_game
) -> None:
    _show(qml_shell, 3)
    fake_controller.settings.set_fixture_states(save_state, game_state)
    qapp.processEvents()

    assert _find(qml_shell, "saveRootBadge").property("label") == expected_save
    assert _find(qml_shell, "gameInstallBadge").property("label") == expected_game


def test_dirty_settings_enable_save_and_cancelled_chooser_is_neutral(
    qapp, qml_shell, fake_controller
) -> None:
    _show(qml_shell, 3)
    button = _find(qml_shell, "saveSettingsButton")
    assert button.property("enabled") is False

    fake_controller.settings.setSaveRoot("C:/edited")
    qapp.processEvents()
    assert button.property("enabled") is True

    _click(_find(qml_shell, "chooseSaveRootButton"))
    qapp.processEvents()
    assert fake_controller.settings.saveRoot == "C:/edited"

    _click(button)
    qapp.processEvents()
    assert button.property("enabled") is False


def test_diagnostics_empty_error_and_readable_event_text(qapp, qml_shell, fake_controller) -> None:
    _show(qml_shell, 4)
    fake_controller.diagnostics.set_fixture_events("", "Log indisponível.")
    qapp.processEvents()
    events = _find(qml_shell, "diagnosticsEvents")
    status = _find(qml_shell, "diagnosticsStatus")
    assert "indisponível" not in events.property("text").lower()
    assert "indisponível" in status.property("text").lower()
    assert events.property("color") != status.property("color")

    fake_controller.diagnostics.set_fixture_events("evento longo\ncom detalhes", "Não foi possível ler o log.")
    qapp.processEvents()
    events = _find(qml_shell, "diagnosticsEvents")
    assert events.property("selectByMouse") is True
    assert events.property("wrapsText") is True
    assert "não foi possível" in _find(qml_shell, "diagnosticsStatus").property("text").lower()


def test_diagnostics_success_status_is_not_rendered_as_an_error(qapp, qml_shell, fake_controller) -> None:
    _show(qml_shell, 4)
    fake_controller.diagnostics.set_fixture_events("evento concluído", "Eventos atualizados.")
    qapp.processEvents()

    assert _find(qml_shell, "diagnosticsStatus").property("color") == QColor("#59C58B")


def test_diagnostics_existing_events_keep_explicit_failure_severity(qapp, tmp_path: Path) -> None:
    log_path = tmp_path / "manager.log"
    log_path.write_text("evento existente\n", encoding="utf-8")
    diagnostics = DiagnosticsViewModel(
        log_path, copier=lambda _text: (_ for _ in ()).throw(RuntimeError)
    )
    diagnostics.refresh()
    diagnostics.copyDiagnostic()
    controller = _DiagnosticsController(diagnostics)
    engine, page = _create_narrow_page(controller, "DiagnosticsPage")
    qapp.processEvents()

    assert _find(page, "diagnosticsStatus").property("color") == QColor("#ED776D")
    page.deleteLater()
    engine.deleteLater()


@pytest.mark.parametrize(
    ("page_name", "page_object_name", "scroll_object_name"),
    [
        ("SettingsPage", "settingsPage", "settingsScrollView"),
        ("DiagnosticsPage", "diagnosticsPage", "diagnosticsScrollView"),
    ],
)
def test_pages_keep_a_single_outer_scroll_view_when_narrow(
    qapp, fake_controller, page_name, page_object_name, scroll_object_name
) -> None:
    engine, page = _create_narrow_page(fake_controller, page_name)
    qapp.processEvents()
    assert page.objectName() == page_object_name
    assert page.property("narrowLayout") is True
    scroll_view = _find(page, scroll_object_name)
    assert scroll_view.property("contentWidth") == scroll_view.property("availableWidth")
    assert sum("ScrollView" in child.metaObject().className() for child in page.findChildren(QObject)) == 1
    page.deleteLater()
    engine.deleteLater()


def test_diagnostic_buttons_reach_python(qapp, qml_shell, fake_controller) -> None:
    _show(qml_shell, 4)
    _click(_find(qml_shell, "copyDiagnosticButton"))
    _click(_find(qml_shell, "openLogsButton"))
    qapp.processEvents()

    assert fake_controller.diagnostics.copy_calls == 1
    assert fake_controller.diagnostics.open_calls == 1
