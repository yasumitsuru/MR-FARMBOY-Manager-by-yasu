"""Contratos do carregamento do shell QML embutido."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Qt, QUrl, qInstallMessageHandler
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest

from mr_farmboy_manager.qml_application import create_engine, run


def test_create_qml_application_preserves_qt_identity(qapp) -> None:
    from mr_farmboy_manager.qml_application import create_qml_application

    application = create_qml_application()

    assert application is qapp
    assert application.organizationName() == "yasu"
    assert application.applicationName() == "MR FARMBOY Manager"


def test_default_backup_root_uses_qt_local_data_location(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import mr_farmboy_manager.qml_application as application

    monkeypatch.setattr(
        application.QStandardPaths,
        "writableLocation",
        lambda _location: str(tmp_path / "local-data"),
    )

    assert application.default_backup_root() == tmp_path / "local-data" / "backups"


def test_default_backup_root_requires_qt_local_data_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mr_farmboy_manager.qml_application as application

    monkeypatch.setattr(application.QStandardPaths, "writableLocation", lambda _location: "")

    with pytest.raises(RuntimeError, match="Diretório local do aplicativo indisponível"):
        application.default_backup_root()


def test_runtime_root_from_environment_is_optional_and_resolved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mr_farmboy_manager.qml_application import runtime_root_from_environment

    monkeypatch.delenv("MR_FARMBOY_RUNTIME_ROOT", raising=False)
    assert runtime_root_from_environment() is None

    configured = tmp_path / "portable" / ".." / "runtime"
    monkeypatch.setenv("MR_FARMBOY_RUNTIME_ROOT", str(configured))

    assert runtime_root_from_environment() == configured.resolve(strict=False)


def _load_engine_recording_qml_messages(fake_controller):
    messages: list[str] = []
    previous = qInstallMessageHandler(lambda _kind, _context, message: messages.append(message))
    try:
        engine = create_engine(fake_controller)
    finally:
        qInstallMessageHandler(previous)
    return engine, messages


def test_qml_engine_loads_main_window(qapp, fake_controller) -> None:
    engine = create_engine(fake_controller)
    roots = engine.rootObjects()

    assert len(roots) == 1
    assert roots[0].objectName() == "mainWindow"
    assert roots[0].property("minimumWidth") == 960
    assert roots[0].findChild(object, "pageStack") is not None


def test_run_returns_nonzero_when_qml_creates_no_root(monkeypatch, qapp, fake_controller) -> None:
    engine = Mock(spec=QQmlApplicationEngine)
    engine.rootObjects.return_value = []
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_qml_application", lambda: qapp)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_controller", lambda **_kwargs: fake_controller)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_engine", lambda controller: engine)

    assert run(start_event_loop=False) == 1
    assert fake_controller.initialize_calls == 0
    assert fake_controller.shutdown_calls == 1


def test_run_shuts_down_controller_after_noninteractive_start(monkeypatch, qapp, fake_controller) -> None:
    engine = Mock(spec=QQmlApplicationEngine)
    engine.rootObjects.return_value = [object()]
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_qml_application", lambda: qapp)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_controller", lambda **_kwargs: fake_controller)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_engine", lambda controller: engine)

    assert run(start_event_loop=False) == 0
    assert fake_controller.initialize_calls == 1
    assert fake_controller.shutdown_calls == 1


def test_run_shuts_down_controller_when_initialize_raises(monkeypatch, qapp, fake_controller) -> None:
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_qml_application", lambda: qapp)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_controller", lambda **_kwargs: fake_controller)
    monkeypatch.setattr(fake_controller, "initialize", lambda: (_ for _ in ()).throw(RuntimeError("init")))

    with pytest.raises(RuntimeError, match="init"):
        run(start_event_loop=False)

    assert fake_controller.shutdown_calls == 1


def test_run_shuts_down_controller_when_engine_creation_raises(monkeypatch, qapp, fake_controller) -> None:
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_qml_application", lambda: qapp)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_controller", lambda **_kwargs: fake_controller)
    monkeypatch.setattr(
        "mr_farmboy_manager.qml_application.create_engine",
        lambda _controller: (_ for _ in ()).throw(RuntimeError("engine")),
    )

    with pytest.raises(RuntimeError, match="engine"):
        run(start_event_loop=False)

    assert fake_controller.initialize_calls == 0
    assert fake_controller.shutdown_calls == 1


def test_minimum_window_width_uses_drawer_navigation(qapp, fake_controller) -> None:
    engine = create_engine(fake_controller)
    root = engine.rootObjects()[0]
    root.setWidth(960)
    qapp.processEvents()

    shell = root.findChild(QObject, "appShell")
    menu = root.findChild(QObject, "navMenuButton")
    assert shell.property("drawerNavigation") is True
    assert shell.property("railNavigation") is False
    assert menu.property("visible") is True


def test_compact_sidebar_has_tab_focus_keyboard_activation_and_no_binding_warning(
    qapp, fake_controller
) -> None:
    engine, messages = _load_engine_recording_qml_messages(fake_controller)
    root = engine.rootObjects()[0]
    previous = qInstallMessageHandler(
        lambda _kind, _context, message: messages.append(message)
    )
    try:
        root.setWidth(1100)
        qapp.processEvents()
    finally:
        qInstallMessageHandler(previous)
    nav_saves = root.findChild(QObject, "navSaves")
    shell = root.findChild(QObject, "appShell")

    assert nav_saves.property("activeFocusOnTab") is True
    nav_saves.forceActiveFocus()
    QTest.keyClick(root, Qt.Key.Key_Return)
    qapp.processEvents()
    assert shell.property("currentIndex") == 1
    shell.setProperty("currentIndex", 0)
    QTest.keyClick(root, Qt.Key.Key_Space)
    qapp.processEvents()
    assert shell.property("currentIndex") == 1
    assert not any("containsMouse is not defined" in message for message in messages)


def test_wide_topbar_shows_fake_dashboard_timestamp_without_qml_warning(
    qapp, fake_controller
) -> None:
    engine, messages = _load_engine_recording_qml_messages(fake_controller)
    root = engine.rootObjects()[0]
    root.setWidth(1366)
    qapp.processEvents()
    timestamp = root.findChild(QObject, "lastUpdatedLabel")

    assert timestamp.property("text") == "10/08/2026 14:30"
    assert timestamp.property("visible") is True
    assert not any("lastUpdatedLabel" in message for message in messages)


@pytest.mark.parametrize(
    "component_name",
    [
        "AppCard",
        "AppButton",
        "MetricCard",
        "StatusBadge",
        "SidebarItem",
        "SectionHeader",
        "EmptyState",
        "InlineMessage",
        "InfoRow",
        "ConfirmActionDialog",
    ],
)
def test_qml_component_compiles_without_import_errors(qapp, component_name: str) -> None:
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl(f"qrc:/qml/components/{component_name}.qml"))

    assert component.isReady(), [str(error) for error in component.errors()]
