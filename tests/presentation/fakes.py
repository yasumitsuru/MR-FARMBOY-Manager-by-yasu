"""Dublês determinísticos usados pelos testes de apresentação."""

from __future__ import annotations

from collections.abc import Callable

from mr_farmboy_manager.presentation.operation_runner import OperationRunner


class ControlledOperationRunner(OperationRunner):
    """Fila manual que permite observar operações sem threads reais."""

    def __init__(self) -> None:
        super().__init__()
        self._next_request_id = 1
        self._pending: list[tuple[int, str, Callable[[], object]]] = []

    def submit(self, name: str, work: Callable[[], object]) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        self._pending.append((request_id, name, work))
        return request_id

    def complete_next(self) -> None:
        request_id, name, work = self._pending.pop(0)
        self.succeeded.emit(request_id, name, work())

    def fail_next(self, message: str) -> None:
        request_id, name, _ = self._pending.pop(0)
        self.failed.emit(request_id, name, message)

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        del timeout_ms
        self._pending.clear()
        return True
