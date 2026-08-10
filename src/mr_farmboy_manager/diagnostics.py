"""Configuração enxuta de diagnóstico persistente da aplicação."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QStandardPaths


LOGGER_NAME = "mr_farmboy_manager"
LOG_FILENAME = "mr-farmboy-manager.log"
_MANAGED_HANDLER_ATTRIBUTE = "_mr_farmboy_manager_handler"


def configure_logging(log_directory: Path | str | None = None) -> Path | None:
    """Configura um arquivo rotativo sem impedir o startup em falha de I/O."""
    if log_directory is None:
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        if not base:
            return None
        directory = Path(base) / "logs"
    else:
        directory = Path(log_directory)

    log_path = directory / LOG_FILENAME
    logger = logging.getLogger(LOGGER_NAME)
    resolved_log_path = log_path.resolve(strict=False)
    for handler in logger.handlers:
        if (
            getattr(handler, _MANAGED_HANDLER_ATTRIBUTE, False)
            and Path(getattr(handler, "baseFilename", "")).resolve(strict=False)
            == resolved_log_path
        ):
            return log_path

    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=1024 * 1024,
            backupCount=3,
            encoding="utf-8",
            delay=True,
        )
    except OSError:
        return None

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    setattr(handler, _MANAGED_HANDLER_ATTRIBUTE, True)
    for previous in list(logger.handlers):
        if getattr(previous, _MANAGED_HANDLER_ATTRIBUTE, False):
            logger.removeHandler(previous)
            previous.close()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return log_path
