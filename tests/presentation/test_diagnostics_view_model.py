"""Contratos de diagnóstico limitado e sem efeitos externos nos testes."""

from __future__ import annotations

from pathlib import Path

from mr_farmboy_manager.presentation.diagnostics_view_model import DiagnosticsViewModel


def test_refresh_reads_only_sanitized_tail_and_adapters_are_injected(tmp_path: Path, qapp) -> None:
    log_path = tmp_path / "logs" / "manager.log"
    log_path.parent.mkdir()
    log_path.write_bytes((b"prefix\n" * 20_000) + b"event\x00unsafe\nlast\n")
    opened: list[Path] = []
    copied: list[str] = []
    vm = DiagnosticsViewModel(log_path, opener=lambda path: opened.append(path) or True, copier=copied.append)

    vm.refresh()
    vm.openLogDirectory()
    vm.copyDiagnostic()

    lines = vm.events.splitlines()
    assert len(lines) <= 50
    assert "\x00" not in vm.events
    assert "event" in vm.events
    assert vm.hasLog is True
    assert opened == [log_path.parent]
    assert copied == [vm.events]


def test_diagnostics_failure_is_public_and_never_exposes_exception(tmp_path: Path, qapp) -> None:
    vm = DiagnosticsViewModel(tmp_path / "missing.log", opener=lambda _path: (_ for _ in ()).throw(RuntimeError("secret")))

    vm.refresh()
    vm.openLogDirectory()

    assert vm.events == ""
    assert vm.hasLog is False
    assert "secret" not in vm.statusMessage


def test_existing_events_keep_error_severity_when_copy_or_open_fails(tmp_path: Path, qapp) -> None:
    log_path = tmp_path / "manager.log"
    log_path.write_text("evento existente\n", encoding="utf-8")
    vm = DiagnosticsViewModel(
        log_path,
        opener=lambda _path: (_ for _ in ()).throw(RuntimeError),
        copier=lambda _text: (_ for _ in ()).throw(RuntimeError),
    )

    vm.refresh()
    vm.copyDiagnostic()
    assert vm.events == "evento existente"
    assert vm.statusSeverity == "error"

    vm.openLogDirectory()
    assert vm.statusSeverity == "error"
