"""Contratos observáveis dos executores de operações serializadas."""

from __future__ import annotations

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from .fakes import ControlledOperationRunner
from mr_farmboy_manager.presentation.operation_runner import QtOperationRunner


def test_controlled_runner_completes_in_submission_order(qapp: QApplication) -> None:
    """Detecta uma fila que execute operações fora da ordem de submissão."""
    runner = ControlledOperationRunner()
    seen: list[tuple[int, str, object]] = []
    runner.succeeded.connect(lambda request, name, value: seen.append((request, name, value)))

    first = runner.submit("refresh", lambda: "first")
    second = runner.submit("details", lambda: "second")
    runner.complete_next()
    runner.complete_next()

    assert seen == [(first, "refresh", "first"), (second, "details", "second")]


def test_controlled_runner_emits_requested_failure_for_next_operation(qapp: QApplication) -> None:
    """Detecta uma falha associada à operação ou solicitação errada."""
    runner = ControlledOperationRunner()
    seen: list[tuple[int, str, str]] = []
    runner.failed.connect(lambda request, name, message: seen.append((request, name, message)))

    request = runner.submit("backup", lambda: None)
    runner.fail_next("indisponível")

    assert seen == [(request, "backup", "indisponível")]


def test_qt_runner_serializes_work_and_reports_monotonic_requests(qapp: QApplication) -> None:
    """Detecta execução paralela ou IDs de requisição repetidos na fila Qt."""
    runner = QtOperationRunner()
    work_order: list[str] = []
    completed: list[tuple[int, str, object]] = []
    event_loop = QEventLoop()

    def record_completion(request: int, name: str, value: object) -> None:
        completed.append((request, name, value))
        if len(completed) == 2:
            event_loop.quit()

    runner.succeeded.connect(record_completion)

    first = runner.submit("refresh", lambda: work_order.append("refresh") or "first")
    second = runner.submit("details", lambda: work_order.append("details") or "second")
    QTimer.singleShot(1_000, event_loop.quit)
    event_loop.exec()
    assert len(completed) == 2
    assert runner.shutdown()

    assert work_order == ["refresh", "details"]
    assert completed == [(first, "refresh", "first"), (second, "details", "second")]


def test_qt_runner_sanitizes_unexpected_work_failure(qapp: QApplication) -> None:
    """Detecta vazamento da exceção interna pela mensagem pública de falha."""
    runner = QtOperationRunner()
    failed: list[tuple[int, str, str]] = []
    runner.failed.connect(lambda request, name, message: failed.append((request, name, message)))

    request = runner.submit("backup", lambda: (_ for _ in ()).throw(RuntimeError("segredo")))
    assert runner.shutdown()
    qapp.processEvents()

    assert failed == [(request, "backup", "Não foi possível concluir a operação.")]
