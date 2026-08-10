"""Execução serial de operações de apresentação fora da thread da interface."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot


LOGGER = logging.getLogger(__name__)
_PUBLIC_FAILURE_MESSAGE = "Não foi possível concluir a operação."


class OperationRunner(QObject):
    """Contrato para operações identificadas e reportadas à apresentação."""

    succeeded = Signal(int, str, object)
    failed = Signal(int, str, str)

    def submit(self, name: str, work: Callable[[], object]) -> int:
        raise NotImplementedError

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        raise NotImplementedError


class _OperationSignals(QObject):
    succeeded = Signal(int, str, object)
    failed = Signal(int, str, str)


class _OperationRunnable(QRunnable):
    def __init__(
        self,
        request_id: int,
        name: str,
        work: Callable[[], object],
        signals: _OperationSignals,
    ) -> None:
        super().__init__()
        self._request_id = request_id
        self._name = name
        self._work = work
        self._signals = signals

    def run(self) -> None:
        try:
            value = self._work()
        except Exception:
            LOGGER.exception("Falha inesperada na operação %s", self._name)
            self._signals.failed.emit(
                self._request_id,
                self._name,
                _PUBLIC_FAILURE_MESSAGE,
            )
        else:
            self._signals.succeeded.emit(self._request_id, self._name, value)


class QtOperationRunner(OperationRunner):
    """Fila Qt de uma única thread para manter a ordem das operações."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._next_request_id = 1
        self._signals = _OperationSignals(self)
        self._signals.succeeded.connect(self._emit_succeeded, Qt.QueuedConnection)
        self._signals.failed.connect(self._emit_failed, Qt.QueuedConnection)

    def submit(self, name: str, work: Callable[[], object]) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        self._pool.start(_OperationRunnable(request_id, name, work, self._signals))
        return request_id

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        self._pool.clear()
        return bool(self._pool.waitForDone(timeout_ms))

    @Slot(int, str, object)
    def _emit_succeeded(self, request_id: int, name: str, value: object) -> None:
        self.succeeded.emit(request_id, name, value)

    @Slot(int, str, str)
    def _emit_failed(self, request_id: int, name: str, message: str) -> None:
        self.failed.emit(request_id, name, message)
