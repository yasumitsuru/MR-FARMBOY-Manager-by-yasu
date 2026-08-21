"""Jornada QML com controller real, limitada integralmente a ``tmp_path``."""
from __future__ import annotations
import hashlib
import logging
from pathlib import Path
from PySide6.QtCore import QMetaObject, QObject, QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from mr_farmboy_manager.backups import create_backup, delete_backup, restore_backup
from mr_farmboy_manager.diagnostics import configure_logging
from mr_farmboy_manager.presentation.app_controller import AppController
from mr_farmboy_manager.presentation.backups_view_model import BackupsViewModel
from mr_farmboy_manager.presentation.settings_view_model import SettingsViewModel
from mr_farmboy_manager.settings import QtSettingsStore
from tests.presentation.fakes import ControlledOperationRunner

def _snapshot_outside(parent: Path, execution_root: Path) -> dict[str, tuple[object, ...]]:
    snapshot = {}
    for path in parent.rglob("*"):
        if path == execution_root or execution_root in path.parents: continue
        stat = path.lstat(); kind = "dir" if path.is_dir() else "file" if path.is_file() else "other"
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if kind == "file" else ""
        snapshot[str(path.relative_to(parent))] = (kind, stat.st_mode, stat.st_size, stat.st_mtime_ns, digest)
    return snapshot

def _find(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name); assert found is not None, name; return found

def _click(item: QObject) -> None:
    assert QMetaObject.invokeMethod(item, "click", Qt.ConnectionType.DirectConnection)

def _click_first_row(root: QObject, list_name: str) -> None:
    item = _find(root, list_name); point = item.mapToScene(QPoint(12, 12)).toPoint()
    QTest.mouseClick(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

def _delegate(root: QObject, property_name: str, value: str) -> QObject:
    found = next((item for item in root.findChildren(QObject) if item.property(property_name) == value), None)
    assert found is not None, f"delegate {property_name}={value}"; return found

def test_qml_entrypoints_use_qml_runner() -> None:
    project_root = Path(__file__).resolve().parents[1]
    assert "mr_farmboy_manager.qml_application:run" in (project_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "from .qml_application import run" in (project_root / "src/mr_farmboy_manager/__main__.py").read_text(encoding="utf-8")
    assert "from mr_farmboy_manager.qml_application import run" in (project_root / "tools/windows_entrypoint.py").read_text(encoding="utf-8")

def test_complete_qml_journey_only_mutates_tmp_path(tmp_path: Path, qapp) -> None:
    from mr_farmboy_manager.qml_application import create_engine
    game_data, runtime = tmp_path / "game_data", tmp_path / "runtime"; slot = game_data / "save_1"; slot.mkdir(parents=True)
    player = slot / "player_data.tres"; original = '[gd_resource type="Resource" format=3]\ncurrent_tutorial = 1\n'; player.write_text(original, encoding="utf-8")
    (slot / "island_main_data.tres").write_text('[gd_resource type="Resource" format=3]\ncurrent_growth_state = 4\nis_planted = true\n', encoding="utf-8")
    external_before, received_paths = _snapshot_outside(tmp_path.parent, tmp_path), []
    def inside(*values):
        for value in values:
            path = Path(value).resolve(strict=False); received_paths.append(path); assert path.is_relative_to(tmp_path)
    def creator(slot_value, active_root, backup_root): inside(slot_value.path, active_root, backup_root); return create_backup(slot_value, active_root, backup_root)
    def restorer(slot_value, active_root, backup_root, backup_id, *, confirmed): inside(slot_value.path, active_root, backup_root); return restore_backup(slot_value, active_root, backup_root, backup_id, confirmed=confirmed)
    def deleter(backup_root, backup_id, *, confirmed): inside(backup_root); return delete_backup(backup_root, backup_id, confirmed=confirmed)
    runner = ControlledOperationRunner(); settings_path = runtime / "settings.ini"
    settings = SettingsViewModel(QtSettingsStore(QSettings(str(settings_path), QSettings.Format.IniFormat)), runtime / "backups")
    backups = BackupsViewModel(runner, runtime / "backups", creator=creator, restorer=restorer, deleter=deleter)
    controller = AppController(settings=settings, backups=backups, runner=runner, log_path=runtime / "logs" / "mr-farmboy-manager.log")
    log_path = configure_logging(runtime / "logs"); assert log_path is not None and log_path.is_relative_to(tmp_path)
    engine = create_engine(controller); root = engine.rootObjects()[0]
    try:
        controller.initialize(); runner.complete_next(); _find(root, "appShell").setProperty("currentIndex", 3)
        field = _find(root, "saveRootField"); field.setProperty("text", str(game_data)); assert QMetaObject.invokeMethod(field, "editingFinished", Qt.ConnectionType.DirectConnection)
        _click(_find(root, "saveSettingsButton")); runner.complete_next(); qapp.processEvents(); assert _find(root, "saveRootMessage").property("text") == "Diretório de saves válido."
        _find(root, "appShell").setProperty("currentIndex", 1); qapp.processEvents(); _click_first_row(root, "saveSlotsList"); runner.complete_next(); qapp.processEvents(); assert controller.saves.details.inspectedFileCount == 2 and _find(root, "saveDetailRecordCount").property("text") == "0"
        _find(root, "appShell").setProperty("currentIndex", 2); qapp.processEvents(); _click(_find(root, "createBackupButton")); runner.complete_next(); runner.complete_next(); qapp.processEvents()
        backup_id = controller.backups.backupsModel.index(0, 0).data(257); _click_first_row(root, "backupsList"); player.write_text(original.replace(" = 1", " = 9"), encoding="utf-8")
        assert controller.backups.canRestore; _click(_find(root, "restoreBackupButton")); _click(_find(root, "confirmDialogConfirmButton")); runner.complete_next();
        if runner._pending: runner.complete_next()
        qapp.processEvents(); assert player.read_text(encoding="utf-8") == original
        _click_first_row(root, "backupsList"); _click(_find(root, "deleteBackupButton")); _click(_find(root, "confirmDialogConfirmButton")); runner.complete_next()
        if runner._pending: runner.complete_next()
        qapp.processEvents(); _find(root, "appShell").setProperty("currentIndex", 1); _click(_find(root, "refreshSavesButton")); runner.complete_next(); qapp.processEvents()
        logging.getLogger("mr_farmboy_manager").info("qml.e2e.completed slot=1")
        for handler in logging.getLogger("mr_farmboy_manager").handlers: handler.flush()
        assert str(tmp_path) not in log_path.read_text(encoding="utf-8"); assert received_paths
    finally:
        assert controller.shutdown() is True; engine.deleteLater()
    assert _snapshot_outside(tmp_path.parent, tmp_path) == external_before
