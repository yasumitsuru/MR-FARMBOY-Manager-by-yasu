"""Logging operacional persistente e sanitizado."""

import logging
from pathlib import Path

import pytest


def test_configure_logging_writes_rotating_diagnostic_file(tmp_path: Path) -> None:
    from mr_farmboy_manager.diagnostics import LOGGER_NAME, configure_logging

    logger = logging.getLogger(LOGGER_NAME)
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    log_directory = tmp_path / "logs"
    private_content = "current_tutorial = 999"

    try:
        log_path = configure_logging(log_directory)
        logger.info("application.startup")
        for handler in logger.handlers:
            handler.flush()

        assert log_path == log_directory / "mr-farmboy-manager.log"
        rendered = log_path.read_text(encoding="utf-8")
        assert "application.startup" in rendered
        assert private_content not in rendered
    finally:
        for handler in list(logger.handlers):
            if handler not in previous_handlers:
                logger.removeHandler(handler)
                handler.close()
        logger.setLevel(previous_level)


def test_run_logs_startup_ready_and_shutdown_without_real_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    import mr_farmboy_manager.qml_application as application

    events: list[str] = []

    class FakeApplication:
        def exec(self) -> int:
            events.append("exec")
            return 0

    class FakeController:
        def initialize(self) -> None:
            events.append("initialize")

        def shutdown(self) -> bool:
            events.append("shutdown")
            return True

    class FakeEngine:
        def rootObjects(self):
            return [object()]

    runtime_root = tmp_path / "runtime"
    captured: dict[str, object] = {}

    def create_application():
        events.append("create_application")
        return FakeApplication()

    def configure_logging(log_directory=None):
        events.append("configure_logging")
        captured["log_directory"] = log_directory

    def settings_store(qsettings=None):
        captured["settings_filename"] = qsettings.fileName()
        return object()

    def create_controller(*, settings_store, backup_root, log_path):
        captured["settings_store"] = settings_store
        captured["backup_root"] = backup_root
        captured["log_path"] = log_path
        return FakeController()

    monkeypatch.setenv("MR_FARMBOY_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(application, "configure_logging", configure_logging)
    monkeypatch.setattr(application, "create_qml_application", create_application)
    monkeypatch.setattr(
        application,
        "create_controller",
        create_controller,
    )
    monkeypatch.setattr(application, "create_engine", lambda _controller: FakeEngine())
    monkeypatch.setattr(application, "QtSettingsStore", settings_store)
    caplog.set_level(logging.INFO, logger="mr_farmboy_manager.qml_application")

    assert application.run(start_event_loop=False) == 0
    assert events == [
        "create_application",
        "configure_logging",
        "initialize",
        "shutdown",
    ]
    assert captured["log_directory"] == runtime_root / "logs"
    assert Path(str(captured["settings_filename"])) == runtime_root / "settings.ini"
    assert captured["backup_root"] == runtime_root / "backups"
    assert [record.getMessage() for record in caplog.records] == [
        "qml.engine.started",
        "qml.load.completed",
        "qml.controller.initialized",
        "qml.application.shutdown exit_code=0",
    ]
