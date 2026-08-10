"""Dublês QML determinísticos, sem I/O e sem diálogos nativos."""

from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot


class FakeViewModel(QObject):
    """Superfície extensível para páginas QML, com estado previsível."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._state = "idle"
        self._status_message = ""
        self._error_message = ""

    @Slot()
    def refresh(self) -> None:
        self._state = "ready"
        self.changed.emit()

    state = Property(str, lambda self: self._state, notify=changed)
    statusMessage = Property(str, lambda self: self._status_message, notify=changed)
    errorMessage = Property(str, lambda self: self._error_message, notify=changed)


class FakeController(QObject):
    """Controller de composição usado pelo bootstrap QML."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.shutdown_calls = 0
        self.initialize_calls = 0
        self._dashboard = FakeViewModel()
        self._saves = FakeViewModel()
        self._backups = FakeViewModel()
        self._settings = FakeViewModel()
        self._diagnostics = FakeViewModel()

    @Slot()
    def initialize(self) -> None:
        self.initialize_calls += 1

    @Slot(result=bool)
    def shutdown(self) -> bool:
        self.shutdown_calls += 1
        return True

    dashboard = Property(QObject, lambda self: self._dashboard, constant=True)
    saves = Property(QObject, lambda self: self._saves, constant=True)
    backups = Property(QObject, lambda self: self._backups, constant=True)
    settings = Property(QObject, lambda self: self._settings, constant=True)
    diagnostics = Property(QObject, lambda self: self._diagnostics, constant=True)
    busy = Property(bool, lambda self: False, constant=True)
