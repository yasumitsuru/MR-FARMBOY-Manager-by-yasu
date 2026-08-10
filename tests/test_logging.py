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
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import mr_farmboy_manager.application as application

    events: list[str] = []

    class FakeApplication:
        def exec(self) -> int:
            events.append("exec")
            return 0

    class FakeWindow:
        def show(self) -> None:
            events.append("show")

    monkeypatch.setattr(application, "configure_logging", lambda: None)
    monkeypatch.setattr(application, "create_application", FakeApplication)
    monkeypatch.setattr(
        application,
        "create_main_window",
        lambda _app, *, settings_store: FakeWindow(),
    )
    monkeypatch.setattr(application, "QtSettingsStore", lambda: object())
    caplog.set_level(logging.INFO, logger="mr_farmboy_manager.application")

    assert application.run() == 0
    assert events == ["show", "exec"]
    assert [record.getMessage() for record in caplog.records] == [
        "application.startup",
        "application.ready",
        "application.shutdown exit_code=0",
    ]
