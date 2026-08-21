"""Leitura limitada de diagnóstico e adaptadores de desktop/clipboard."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication


_MAX_LOG_TAIL_BYTES = 64 * 1024
_MAX_EVENTS = 50
Opener = Callable[[Path], bool]
Copier = Callable[[str], None]


class DiagnosticsViewModel(QObject):
    """Expõe logs curtos e sanitizados, sem vazar erros de I/O para o QML."""

    changed = Signal()

    def __init__(
        self,
        log_path: Path | str | None,
        *,
        opener: Opener | None = None,
        copier: Copier | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._log_path = Path(log_path) if log_path else None
        self._opener = opener or self._open_directory
        self._copier = copier or self._copy_to_clipboard
        self._events = ""
        self._status_message = ""
        self._status_severity = "neutral"

    @Slot()
    def refresh(self) -> None:
        events = self._read_events()
        unavailable = not events and not self.hasLog
        self._replace(
            events=events,
            status_message="Log indisponível." if unavailable else "",
            status_severity="error" if unavailable else "neutral",
        )

    @Slot()
    def openLogDirectory(self) -> None:
        if self._log_path is None:
            self._replace(status_message="Pasta de logs indisponível.", status_severity="error")
            return
        try:
            opened = bool(self._opener(self._log_path.parent))
        except Exception:
            opened = False
        self._replace(
            status_message="" if opened else "Não foi possível abrir a pasta de logs.",
            status_severity="neutral" if opened else "error",
        )

    @Slot()
    def copyDiagnostic(self) -> None:
        try:
            self._copier(self._events)
        except Exception:
            self._replace(status_message="Não foi possível copiar o diagnóstico.", status_severity="error")
            return
        self._replace(status_message="Diagnóstico copiado.", status_severity="success")

    def _read_events(self) -> str:
        if self._log_path is None:
            return ""
        try:
            with self._log_path.open("rb") as stream:
                stream.seek(0, 2)
                size = stream.tell()
                stream.seek(max(0, size - _MAX_LOG_TAIL_BYTES))
                text = stream.read(_MAX_LOG_TAIL_BYTES).decode("utf-8", errors="replace")
        except (OSError, ValueError):
            return ""
        return "\n".join(self._sanitize_line(line) for line in text.splitlines()[-_MAX_EVENTS:])

    @staticmethod
    def _sanitize_line(value: str) -> str:
        return "".join(char if char == "\t" or char.isprintable() else "�" for char in value)

    @staticmethod
    def _open_directory(path: Path) -> bool:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @staticmethod
    def _copy_to_clipboard(value: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            raise RuntimeError
        clipboard.setText(value)

    def _replace(
        self,
        *,
        events: str | None = None,
        status_message: str | None = None,
        status_severity: str | None = None,
    ) -> None:
        changed = False
        if events is not None and events != self._events:
            self._events = events
            changed = True
        if status_message is not None and status_message != self._status_message:
            self._status_message = status_message
            changed = True
        if status_severity is not None and status_severity != self._status_severity:
            self._status_severity = status_severity
            changed = True
        if changed:
            self.changed.emit()

    logPathLabel = Property(str, lambda self: str(self._log_path) if self._log_path else "Não disponível", constant=True)
    logDirectoryLabel = Property(str, lambda self: str(self._log_path.parent) if self._log_path else "Não disponível", constant=True)
    events = Property(str, lambda self: self._events, notify=changed)
    hasLog = Property(bool, lambda self: self._log_path is not None and self._log_path.is_file(), notify=changed)
    statusMessage = Property(str, lambda self: self._status_message, notify=changed)
    statusSeverity = Property(str, lambda self: self._status_severity, notify=changed)


__all__ = ["Copier", "DiagnosticsViewModel", "Opener"]
