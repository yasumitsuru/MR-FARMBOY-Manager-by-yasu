"""Invariantes de layout para a janela QML desktop."""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QElapsedTimer, QObject, QMetaObject, QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest


SIZES = ((1280, 720), (1366, 768), (1600, 900), (1920, 1080))


def _find(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, f"Ponto estável ausente: {name}"
    return found


def _click(item: QObject) -> None:
    assert QMetaObject.invokeMethod(item, "click", Qt.ConnectionType.DirectConnection)


def _bounds(item: QQuickItem, ancestor: QQuickItem) -> tuple[float, float, float, float]:
    origin = item.mapToItem(ancestor, QPointF(0, 0))
    return origin.x(), origin.y(), item.width(), item.height()


def _assert_valid_geometry(item: QObject) -> None:
    assert isinstance(item, QQuickItem)
    values = (item.x(), item.y(), item.width(), item.height())
    assert all(math.isfinite(value) and value >= 0 for value in values)


def _wait_for_color(qapp, item: QObject, expected: QColor, timeout_ms: int = 1000) -> None:
    timer = QElapsedTimer()
    timer.start()
    actual = item.property("color")
    while actual != expected and timer.elapsed() < timeout_ms:
        qapp.processEvents()
        QTest.qWait(10)
        actual = item.property("color")
    assert actual == expected, (
        f"A cor animada não alcançou {expected.name()} em {timeout_ms} ms; "
        f"cor atual: {actual.name()}."
    )


@pytest.mark.parametrize(("width", "height"), SIZES)
def test_dashboard_and_saves_headers_keep_title_and_action_separate_at_desktop_sizes(
    qapp, qml_shell, width: int, height: int
) -> None:
    qml_shell.setWidth(width)
    qml_shell.setHeight(height)

    for page_index, header_name, title_name, action_name in (
        (0, "dashboardHeader", "dashboardHeaderTitle", "dashboardHeaderAction"),
        (1, "savesLedgerHeader", "savesLedgerHeaderTitle", "savesLedgerHeaderAction"),
    ):
        _find(qml_shell, "appShell").setProperty("currentIndex", page_index)
        qapp.processEvents()
        header = _find(qml_shell, header_name)
        title = _find(header, title_name)
        action = _find(header, action_name)
        title_x, title_y, title_width, title_height = _bounds(title, header)
        action_x, action_y, action_width, action_height = _bounds(action, header)

        assert title_width > 0 and title_height > 0
        assert action_width > 0 and action_height > 0
        overlaps = (
            title_x < action_x + action_width
            and action_x < title_x + title_width
            and title_y < action_y + action_height
            and action_y < title_y + title_height
        )
        assert not overlaps


@pytest.mark.parametrize(("width", "height"), SIZES)
def test_named_page_layout_items_have_finite_geometry_and_valid_scroll_width(
    qapp, qml_shell, width: int, height: int
) -> None:
    qml_shell.setWidth(width)
    qml_shell.setHeight(height)

    for page_index, names, scroll_name in (
        (0, ("dashboardPage", "dashboardHeader", "dashboardCropPanel"), None),
        (1, ("savesPage", "savesLedgerHeader", "refreshSavesButton", "saveDetailsPanel"), None),
        (2, ("backupsPage", "createBackupButton", "backupsList"), "backupsScrollView"),
        (3, ("settingsPage", "saveRootField", "saveSettingsButton"), "settingsScrollView"),
        (4, ("diagnosticsPage", "diagnosticsEvents", "diagnosticsStatus"), "diagnosticsScrollView"),
    ):
        _find(qml_shell, "appShell").setProperty("currentIndex", page_index)
        qapp.processEvents()
        for name in names:
            _assert_valid_geometry(_find(qml_shell, name))
        if scroll_name:
            scroll = _find(qml_shell, scroll_name)
            assert scroll.property("availableWidth") >= 0
            assert scroll.property("contentWidth") == scroll.property("availableWidth")


def test_delete_confirmation_uses_solid_danger_surface_with_contrasting_text(
    qapp, qml_shell, fake_controller
) -> None:
    fake_controller.backups.model_fixture_backup("backup-id")
    fake_controller.backups.selectBackup("backup-id")
    _find(qml_shell, "appShell").setProperty("currentIndex", 2)
    _click(_find(qml_shell, "deleteBackupButton"))
    qapp.processEvents()

    danger = _find(qml_shell, "confirmDialogConfirmButton")
    background = danger.property("background")
    content = danger.property("contentItem")
    assert danger.property("variant") == "danger"
    _wait_for_color(qapp, background, QColor("#ED776D"))
    assert content.property("color") == QColor("#0B1410")
