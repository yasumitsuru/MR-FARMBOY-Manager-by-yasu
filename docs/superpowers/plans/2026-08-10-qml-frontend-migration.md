# QML Frontend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Qt Widgets frontend with a modern, responsive QML/Qt Quick interface while preserving the tested Python backend and filesystem safety guarantees.

**Architecture:** Introduce page-scoped `QObject` ViewModels and `QAbstractListModel` adapters behind one `AppController`. A serialized Qt worker runner keeps filesystem operations off the render thread, while QML owns navigation, layout, visual state and confirmations. The QML application runs beside Widgets until parity, then becomes the entry point; Widgets are removed only after integration, build, smoke and visual gates pass.

**Tech Stack:** Python 3.12, PySide6 6.5+, Qt Core, Qt GUI, Qt QML, Qt Quick, Qt Quick Layouts, Qt Quick Controls 2, pytest 9, PyInstaller 6, Windows.

**Design spec:** `docs/superpowers/specs/2026-08-10-qml-frontend-migration-design.md`

## Global Constraints

- Work directly on the current `main` branch; do not create a worktree or parallel branch.
- Before every task, run `/closing-stale-subagents`, confirm `pending_count = 0`, and keep at most one subagent active.
- Use `/test-driven-development` for every behavioral change: RED, minimal GREEN, then refactor only while green.
- Use `/systematic-debugging` before changing code in response to an unexpected failure, crash, QML load error or broken binding.
- Use one fresh implementer and then one fresh reviewer per task, sequentially; close and audit handles between dispatches.
- Run the targeted tests and `\.venv\Scripts\python.exe -m pytest` before every commit.
- Before every commit, run `/verification-before-completion`, `git diff --check`, inspect `git diff` and confirm `locais.txt` is not staged.
- One logical task equals one conventional commit; push immediately, run `git fetch origin`, and confirm `HEAD == origin/main` with no ahead/behind.
- Never amend or rebase a published task; later corrections get a new `fix(...)` commit.
- Never write, restore, rename or delete real saves or the real game installation; all mutable tests use `tmp_path`.
- Automated tests must not open `QFileDialog`, `QMessageBox` or any other modal window.
- QML never performs filesystem or business operations in JavaScript.
- Preserve PySide6/Qt LGPLv3 compatibility; add no GPL-only, paid or proprietary dependency.
- The UI uses only real parsed values; missing values render as unavailable rather than invented numbers.
- The dark-first tokens, page behavior, breakpoints and accessibility requirements in the design spec are normative.

## File Responsibility Map

### Presentation Python

- `presentation/operation_runner.py`: serialized worker queue and completion signals.
- `presentation/formatters.py`: stable size, date and optional-value labels.
- `presentation/save_slots_model.py`, `backups_model.py`, `growth_states_model.py`: stable QML roles.
- `presentation/saves_view_model.py`: save refresh, selection and details.
- `presentation/backups_view_model.py`: backup list and safe mutations.
- `presentation/settings_view_model.py`: editable configuration and native choosers.
- `presentation/dashboard_view_model.py`: real aggregate dashboard values.
- `presentation/diagnostics_view_model.py`: bounded logs and desktop actions.
- `presentation/app_controller.py`: composition, cross-page state and auto-refresh.
- `qml_application.py`: QML bootstrap and portable runtime wiring.

### QML and resources

- `qml/Main.qml`, `qml/Theme.qml`, `qml/qmldir`: window, tokens and module metadata.
- `qml/components/*.qml`: shell, cards, buttons, badges, messages and confirmations.
- `qml/pages/*.qml`: Dashboard, Saves, Backups, Settings and Diagnostics.
- `resources/qml.qrc` and `_qml_resources.py`: embedded resources and generated registry.

### Test support

- `tests/presentation/fakes.py`: deterministic runner and desktop adapters.
- `tests/presentation/test_*.py`: ViewModel/model contracts.
- `tests/qml/test_*.py`: offscreen engine, page and binding contracts.
- `tests/test_qml_e2e.py`: complete journey on a temporary filesystem.

---

### Task 1: Normalize an individual save slot to its global root

**Files:**

- Modify: `src/mr_farmboy_manager/manual_paths.py`
- Modify: `tests/test_manual_paths.py`

**Interfaces:**

- Produces `DirectoryValidationCode.NORMALIZED = "normalized"`.
- Produces `validate_save_root_path(value: Path | str | None) -> DirectoryValidationResult`.
- Changes `DirectoryValidationResult.is_valid` to accept `VALID` and `NORMALIZED`.
- Changes `load_save_slot_summaries()` to use the effective root.

- [ ] **Step 1: Write RED regression tests**

```python
def test_load_normalizes_recognized_slot_to_game_data(tmp_path: Path) -> None:
    root = tmp_path / "game_data"
    slot = root / "save_1"
    slot.mkdir(parents=True)
    (slot / "crop.tres").write_text("[gd_resource]", encoding="utf-8")
    result = load_save_slot_summaries(slot)
    assert result.validation.code is DirectoryValidationCode.NORMALIZED
    assert result.validation.path == root
    assert [item.slot.number for item in result.summaries] == [1]


def test_empty_existing_root_remains_valid_and_empty(tmp_path: Path) -> None:
    root = tmp_path / "game_data"
    root.mkdir()
    result = load_save_slot_summaries(root)
    assert result.validation.code is DirectoryValidationCode.VALID
    assert result.summaries == ()


def test_non_slot_directory_never_walks_to_parent(tmp_path: Path) -> None:
    selected = tmp_path / "custom"
    selected.mkdir()
    (tmp_path / "save_2").mkdir()
    result = load_save_slot_summaries(selected)
    assert result.validation.path == selected
    assert result.validation.code is DirectoryValidationCode.VALID
```

- [ ] **Step 2: Run RED**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_manual_paths.py -q`

Expected: normalization fails because the new code and function do not exist.

- [ ] **Step 3: Implement the narrow normalizer**

```python
_SAVE_SLOT_NAME = re.compile(r"^save_(\d+)$")


def validate_save_root_path(value: Path | str | None) -> DirectoryValidationResult:
    validation = validate_directory_path(value)
    if not validation.is_valid or validation.path is None:
        return validation
    match = _SAVE_SLOT_NAME.fullmatch(validation.path.name)
    if match is None:
        return validation
    slot_number = int(match.group(1))
    candidates = discover_save_slots(validation.path.parent)
    if any(candidate.number == slot_number and candidate.path == validation.path for candidate in candidates):
        return DirectoryValidationResult(DirectoryValidationCode.NORMALIZED, validation.path.parent)
    return validation
```

Import `re` and `discover_save_slots`. Do not call `resolve()` and do not read or mutate save contents during normalization.

- [ ] **Step 4: Run GREEN**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_manual_paths.py tests/test_save_slots.py tests/test_configuration_refresh_ui.py -q`

Expected: all selected tests pass and empty-root behavior is preserved.

- [ ] **Step 5: Verify, commit and synchronize**

```powershell
.\.venv\Scripts\python.exe -m pytest
git diff --check
git status --short
git add -- src/mr_farmboy_manager/manual_paths.py tests/test_manual_paths.py
git commit -m "fix(paths): normalize selected save slot root"
git push origin main
git fetch origin
git status -sb
```

### Task 2: Add serialized operations and QML list models

**Files:**

- Create: `src/mr_farmboy_manager/presentation/__init__.py`
- Create: `src/mr_farmboy_manager/presentation/operation_runner.py`
- Create: `src/mr_farmboy_manager/presentation/formatters.py`
- Create: `src/mr_farmboy_manager/presentation/save_slots_model.py`
- Create: `src/mr_farmboy_manager/presentation/backups_model.py`
- Create: `src/mr_farmboy_manager/presentation/growth_states_model.py`
- Create: `tests/presentation/__init__.py`
- Create: `tests/presentation/fakes.py`
- Create: `tests/presentation/test_operation_runner.py`
- Create: `tests/presentation/test_models.py`
- Modify: `tests/conftest.py`

**Interfaces:**

- Produces `OperationRunner(QObject)` with `succeeded(int, str, object)` and `failed(int, str, str)`.
- Produces `QtOperationRunner.submit(name, work) -> int` and `shutdown(timeout_ms=5000) -> bool`.
- Produces `ControlledOperationRunner.complete_next()` and `fail_next(message)` for deterministic tests.
- Produces stable save roles `slotId`, `displayName`, `slotNumber`, `recordCount`, `pathLabel`, `selected`.
- Produces stable backup roles `backupId`, `slotId`, `slotLabel`, `createdAtLabel`, `sizeLabel`, `integrityLabel`, `selected`.
- Produces growth roles `label`, `value`, `total`, `ratio`.

- [ ] **Step 1: Write RED runner and model tests**

```python
def test_controlled_runner_completes_in_submission_order(qapp) -> None:
    runner = ControlledOperationRunner()
    seen: list[tuple[int, str, object]] = []
    runner.succeeded.connect(lambda request, name, value: seen.append((request, name, value)))
    first = runner.submit("refresh", lambda: "first")
    second = runner.submit("details", lambda: "second")
    runner.complete_next()
    runner.complete_next()
    assert seen == [(first, "refresh", "first"), (second, "details", "second")]


def test_save_model_exposes_stable_roles(tmp_path: Path) -> None:
    summary = SaveSlotSummary(SaveSlot(2, tmp_path / "save_2"), 7)
    model = SaveSlotsModel()
    model.replace((summary,))
    index = model.index(0, 0)
    assert model.data(index, SaveSlotsModel.SlotIdRole) == "save_2"
    assert model.data(index, SaveSlotsModel.RecordCountRole) == 7
    assert model.roleNames()[SaveSlotsModel.SelectedRole] == b"selected"
```

Also cover backup order, selected-row notifications, empty reset, size/date labels, growth ratios and zero totals.

- [ ] **Step 2: Run RED**

Run: `\.venv\Scripts\python.exe -m pytest tests/presentation/test_operation_runner.py tests/presentation/test_models.py -q`

Expected: collection fails because the presentation package is absent.

- [ ] **Step 3: Implement the runner**

```python
class OperationRunner(QObject):
    succeeded = Signal(int, str, object)
    failed = Signal(int, str, str)

    def submit(self, name: str, work: Callable[[], object]) -> int:
        raise NotImplementedError

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        raise NotImplementedError


class QtOperationRunner(OperationRunner):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._next_request_id = 1
```

Use a private `QRunnable` and private signals. Log unexpected exceptions and emit only `"Não foi possível concluir a operação."`.

- [ ] **Step 4: Implement models and test fake**

Use `beginResetModel()/endResetModel()` for replacement and `dataChanged` only for rows whose selection changes. Keep immutable tuples and Python object maps internally. `pathLabel` is only the basename; `integrityLabel` is `"Íntegro"` for discovered records.

Add one session-scoped `qapp` fixture to `tests/conftest.py` that reuses or creates `QApplication([])`. It must not call `exec()` and must coexist with the modal-dialog guard.

- [ ] **Step 5: Run GREEN and synchronize**

Run targeted tests, then the full suite and diff checks. Commit `feat(qml): add presentation models and operation runner`, push, fetch and confirm synchronization.

### Task 3: Implement SavesViewModel and structured details

**Files:**

- Create: `src/mr_farmboy_manager/presentation/saves_view_model.py`
- Create: `tests/presentation/test_saves_view_model.py`

**Interfaces:**

- Consumes `OperationRunner`, `SaveSlotsModel`, `GrowthStatesModel`, `load_save_slot_summaries`, `inspect_save_slot`.
- Produces `SaveDetailsViewModel` properties `recordCount`, `plantedCount`, `wateredCount`, `fertilizedCount`, `maturedCount`, `harvestableCount`, `deadCount`, `inspectedFileCount`, `failedFileCount`, `latestModifiedLabel`, `hasCropProgress`, `hasPlayerProgress`, `growthStatesModel`.
- Produces `SavesViewModel` properties `state`, `detailsState`, `selectedSlotId`, `statusMessage`, `errorMessage`, `canRefresh`, `canCreateBackup`, `slotsModel`, `details`.
- Produces slots `setSaveRoot(str)`, `refresh()`, `selectSlot(str)`, `clearSelection()` and Python signal `selectedSummaryChanged(object)`.

- [ ] **Step 1: Write RED state tests**

```python
def test_refresh_moves_loading_to_ready_and_preserves_selection(tmp_path: Path, qapp) -> None:
    runner = ControlledOperationRunner()
    vm = SavesViewModel(runner, loader=lambda _path: loaded_result(tmp_path, (1, 2)))
    vm.setSaveRoot(str(tmp_path))
    vm.refresh()
    assert vm.state == "loading"
    runner.complete_next()
    vm.selectSlot("save_2")
    assert vm.state == "ready"
    assert vm.selectedSlotId == "save_2"
    assert vm.canCreateBackup is True


def test_stale_detail_result_cannot_replace_new_selection(tmp_path: Path, qapp) -> None:
    runner = ControlledOperationRunner()
    vm = configured_saves_view_model(runner, tmp_path)
    vm.selectSlot("save_1")
    vm.selectSlot("save_2")
    runner.complete_request(1)
    assert vm.selectedSlotId == "save_2"
    assert vm.detailsState == "loading"
```

Also cover idle, empty, error, removed selection, sanitized failure, optional metrics and zero growth totals.

- [ ] **Step 2: Run RED**

Run: `\.venv\Scripts\python.exe -m pytest tests/presentation/test_saves_view_model.py -q`

Expected: module import fails.

- [ ] **Step 3: Implement request generations**

```python
@Slot()
def refresh(self) -> None:
    if not self._save_root or self._refresh_request is not None:
        return
    self._set_state("loading")
    self._refresh_generation += 1
    generation = self._refresh_generation
    self._refresh_request = self._runner.submit(
        f"saves.refresh:{generation}",
        lambda: self._loader(self._save_root),
    )
```

Connect runner signals once, match request IDs, discard details whose slot/generation no longer matches, and notify only on actual changes. QML never receives `Path` or raw domain DTOs.

- [ ] **Step 4: Run GREEN and synchronize**

Run the new tests plus `tests/test_save_details.py` and `tests/test_save_slot_summaries.py`, then full pytest and diff checks. Commit `feat(qml): add saves view model`, push, fetch and confirm synchronization.

### Task 4: Implement BackupsViewModel and safe confirmations

**Files:**

- Create: `src/mr_farmboy_manager/presentation/backups_view_model.py`
- Create: `tests/presentation/test_backups_view_model.py`

**Interfaces:**

- Consumes `OperationRunner`, `BackupsModel`, `SaveSlotSummary` and existing backup services.
- Produces properties `state`, `mutationState`, `selectedBackupId`, `statusMessage`, `errorMessage`, `canCreate`, `canRestore`, `canDelete`, `backupsModel`.
- Produces signal `confirmationRequested(str action, str backupId, str title, str message)`.
- Produces slots `setSelectedSummary(object)`, `refresh()`, `selectBackup(str)`, `createForSelectedSlot()`, `requestRestore()`, `requestDelete()`, `confirmAction(str, str)`, `cancelConfirmation()`.

- [ ] **Step 1: Write RED action tests**

```python
def test_restore_requires_matching_confirmation(tmp_path: Path, qapp) -> None:
    restorer = Mock(return_value=restore_success())
    vm, runner, record = ready_backups_vm(tmp_path, restorer=restorer)
    vm.selectBackup(record.backup_id)
    vm.requestRestore()
    vm.confirmAction("restore", "different-id")
    assert restorer.call_count == 0
    assert vm.mutationState == "idle"


def test_delete_runs_confirmed_service(tmp_path: Path, qapp) -> None:
    deleter = Mock(return_value=delete_success("backup-id"))
    vm, runner, record = ready_backups_vm(tmp_path, deleter=deleter)
    vm.selectBackup(record.backup_id)
    vm.requestDelete()
    vm.confirmAction("delete", record.backup_id)
    assert vm.mutationState == "deleting"
    runner.complete_next()
    deleter.assert_called_once_with(tmp_path / "backups", record.backup_id, confirmed=True)
```

Cover create without selection, discovery error, selection preservation on failure, refresh after success, cleanup-pending success and sanitized exceptions.

- [ ] **Step 2: Run RED**

Run: `\.venv\Scripts\python.exe -m pytest tests/presentation/test_backups_view_model.py -q`

Expected: module import fails.

- [ ] **Step 3: Implement serialized mutations**

Use exactly these domain calls:

```python
create_backup(summary.slot, summary.slot.path.parent, backup_root)
discover_backups(backup_root)
restore_backup(summary.slot, summary.slot.path.parent, backup_root, backup_id, confirmed=True)
delete_backup(backup_root, backup_id, confirmed=True)
```

Disable refresh and conflicting actions until completion. Revalidate selected summary, backup ID and action immediately before submit. After successful create/restore/delete, enqueue exactly one discovery refresh.

- [ ] **Step 4: Run GREEN and synchronize**

Run the new tests plus `tests/test_backups.py`, `tests/test_backup_restore.py`, `tests/test_backup_delete.py`, full pytest and diff checks. Commit `feat(qml): add backups view model`, push, fetch and confirm synchronization.

### Task 5: Implement SettingsViewModel and native chooser adapters

**Files:**

- Create: `src/mr_farmboy_manager/presentation/settings_view_model.py`
- Create: `tests/presentation/test_settings_view_model.py`

**Interfaces:**

- Consumes `SettingsStore`, `AppSettings`, `validate_directory_path`, `validate_save_root_path`.
- Produces properties `saveRoot`, `gameInstallRoot`, `backupRootLabel`, `saveRootState`, `gameInstallState`, `saveRootMessage`, `gameInstallMessage`, `hasUnsavedChanges`, `canSave`.
- Produces slots `setSaveRoot(str)`, `setGameInstallRoot(str)`, `chooseSaveRoot()`, `chooseGameInstallRoot()`, `save()`, `reload()`.
- Produces signal `settingsApplied(str saveRoot, str gameInstallRoot)`.

- [ ] **Step 1: Write RED persistence tests**

```python
def test_normalized_slot_is_displayed_and_persisted_as_root(tmp_path: Path, qapp) -> None:
    root = tmp_path / "game_data"
    (root / "save_1").mkdir(parents=True)
    store = FakeSettingsStore(AppSettings("", ""))
    vm = SettingsViewModel(store, backup_root=tmp_path / "backups")
    vm.setSaveRoot(str(root / "save_1"))
    vm.save()
    assert vm.saveRoot == str(root)
    assert vm.saveRootState == "valid"
    assert "normalizada" in vm.saveRootMessage.lower()
    assert store.saved == AppSettings(str(root), "")
```

Also cover unset, invalid, valid empty root, chooser cancellation, game path, invalid values not replacing persisted operational settings, reload and dirty state.

- [ ] **Step 2: Run RED**

Run: `\.venv\Scripts\python.exe -m pytest tests/presentation/test_settings_view_model.py -q`

Expected: module import fails.

- [ ] **Step 3: Implement validation and injected choosers**

```python
DirectoryChooser = Callable[[], str | None]


class SettingsViewModel(QObject):
    settingsApplied = Signal(str, str)

    def __init__(
        self,
        store: SettingsStore,
        backup_root: Path,
        save_chooser: DirectoryChooser | None = None,
        game_chooser: DirectoryChooser | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
```

Default choosers call `QFileDialog.getExistingDirectory`; tests inject fakes. Persist the effective normalized save root. `canSave` is false when a non-empty configured path is invalid.

- [ ] **Step 4: Run GREEN and synchronize**

Run the new tests plus `tests/test_settings.py`, then full pytest and diff checks. Commit `feat(qml): add settings view model`, push, fetch and confirm synchronization.

### Task 6: Implement dashboard, diagnostics and AppController

**Files:**

- Create: `src/mr_farmboy_manager/presentation/dashboard_view_model.py`
- Create: `src/mr_farmboy_manager/presentation/diagnostics_view_model.py`
- Create: `src/mr_farmboy_manager/presentation/app_controller.py`
- Create: `tests/presentation/test_dashboard_view_model.py`
- Create: `tests/presentation/test_diagnostics_view_model.py`
- Create: `tests/presentation/test_app_controller.py`

**Interfaces:**

- Produces `DashboardViewModel.update(slot_count, selected_details, backups, configuration_state, updated_at)`.
- Produces dashboard properties `slotCount`, `backupCount`, `selectedSlotLabel`, `lastBackupLabel`, `lastUpdatedLabel`, `configurationState`, seven crop metrics and `hasSelectedSlot`.
- Produces diagnostics properties `logPathLabel`, `logDirectoryLabel`, `events`, `hasLog`, `statusMessage`; slots `refresh()`, `openLogDirectory()`, `copyDiagnostic()`.
- Produces `AppController` properties `saves`, `backups`, `settings`, `dashboard`, `diagnostics`, `busy`; slots `initialize()`, `shutdown()` and a timer interval of exactly 300000 ms.

- [ ] **Step 1: Write RED aggregate and timer tests**

```python
def test_dashboard_uses_real_crop_metrics(qapp) -> None:
    vm = DashboardViewModel()
    vm.update(2, details_with_crop(planted=8, watered=5), two_backups(), "valid", fixed_time())
    assert vm.slotCount == 2
    assert vm.plantedCount == 8
    assert vm.wateredCount == 5
    assert not hasattr(vm, "money")


def test_controller_timer_skips_active_mutation(qapp) -> None:
    controller = controller_with_fakes()
    assert controller.autoRefreshInterval == 300000
    controller.backups.setMutationStateForTest("restoring")
    controller.triggerAutoRefreshForTest()
    assert controller.saves.refresh_calls == 0
```

Diagnostics tests use a UTF-8 log under `tmp_path`, assert at most 50 sanitized lines, and inject open/copy callables.

- [ ] **Step 2: Run RED**

Run the three new test files; expected imports fail.

- [ ] **Step 3: Implement bounded diagnostics and composition**

Read at most 64 KiB from the log tail, replace unsafe control characters, expose no raw exceptions, and call `QDesktopServices` only through an injected opener. `AppController.initialize()` loads settings, applies the save root, refreshes page state, starts the timer and connects save selection to backups and dashboard recomputation.

- [ ] **Step 4: Run GREEN and synchronize**

Run the three new files plus `tests/test_logging.py`, full pytest and diff checks. Commit `feat(qml): add application controller and dashboard state`, push, fetch and confirm synchronization.

### Task 7: Create QML bootstrap, resources, design system and shell

**Required skill before implementation:** `frontend-design`.

**Files:**

- Create: `src/mr_farmboy_manager/qml_application.py`
- Create: `src/mr_farmboy_manager/qml/Theme.qml`
- Create: `src/mr_farmboy_manager/qml/qmldir`
- Create: `src/mr_farmboy_manager/qml/Main.qml`
- Create: `src/mr_farmboy_manager/qml/components/AppShell.qml`
- Create: `src/mr_farmboy_manager/qml/components/AppCard.qml`
- Create: `src/mr_farmboy_manager/qml/components/AppButton.qml`
- Create: `src/mr_farmboy_manager/qml/components/MetricCard.qml`
- Create: `src/mr_farmboy_manager/qml/components/StatusBadge.qml`
- Create: `src/mr_farmboy_manager/qml/components/SidebarItem.qml`
- Create: `src/mr_farmboy_manager/qml/components/SectionHeader.qml`
- Create: `src/mr_farmboy_manager/qml/components/EmptyState.qml`
- Create: `src/mr_farmboy_manager/qml/components/InlineMessage.qml`
- Create: `src/mr_farmboy_manager/qml/components/InfoRow.qml`
- Create: `src/mr_farmboy_manager/qml/components/ConfirmActionDialog.qml`
- Create: `src/mr_farmboy_manager/resources/qml.qrc`
- Create: `src/mr_farmboy_manager/_qml_resources.py`
- Create: `tests/qml/__init__.py`
- Create: `tests/qml/fakes.py`
- Create: `tests/qml/conftest.py`
- Create: `tests/qml/test_qml_bootstrap.py`

**Interfaces:**

- Produces `create_qml_application() -> QApplication`, `create_controller()`, `create_engine(controller)`, `run(*, start_event_loop: bool = True) -> int`.
- Exposes context property `appController` before loading `qrc:/qml/Main.qml`.
- Produces `qml_shell` and `fake_controller` fixtures with deterministic child objects matching all ViewModel properties, signals and slots used by pages.
- Stable names: `mainWindow`, `pageStack`, `navDashboard`, `navSaves`, `navBackups`, `navSettings`, `navDiagnostics`.
- Initial 1366×768, minimum 960×640; sidebar breakpoints 1200 and 900.

- [ ] **Step 1: Write RED bootstrap tests**

```python
def test_qml_engine_loads_main_window(qapp, fake_controller) -> None:
    engine = create_engine(fake_controller)
    roots = engine.rootObjects()
    assert len(roots) == 1
    assert roots[0].objectName() == "mainWindow"
    assert roots[0].property("minimumWidth") == 960
```

Also test nonzero return when no root object is created and controller shutdown on exit.

- [ ] **Step 2: Run RED with offscreen**

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest tests/qml/test_qml_bootstrap.py -q
```

Expected: `qml_application` is absent.

- [ ] **Step 3: Implement bootstrap and embedded resources**

```python
def create_engine(controller: AppController) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("appController", controller)
    engine.load(QUrl("qrc:/qml/Main.qml"))
    return engine
```

Import `_qml_resources` and generate it with:

```powershell
.\.venv\Scripts\pyside6-rcc.exe src\mr_farmboy_manager\resources\qml.qrc -o src\mr_farmboy_manager\_qml_resources.py
```

- [ ] **Step 4: Implement the shell and tokens**

`Theme.qml` contains every token from the spec. `AppShell` uses `RowLayout`, 232 px sidebar, 80 px rail and drawer below 900 px. `StackLayout` preserves pages. Components expose semantic properties, keyboard focus and no hardcoded color outside `Theme.qml`.

```qml
ApplicationWindow {
    objectName: "mainWindow"
    width: 1366
    height: 768
    minimumWidth: 960
    minimumHeight: 640
    visible: true
    color: Theme.background
    AppShell { anchors.fill: parent; controller: appController }
}
```

- [ ] **Step 5: Run GREEN and synchronize**

Run bootstrap tests and assert no missing import, load error or binding loop. Regenerate resources, run full pytest/diff checks, commit `feat(qml): add design system and application shell`, push, fetch and confirm synchronization.

### Task 8: Build Dashboard and Saves pages

**Files:**

- Create: `src/mr_farmboy_manager/qml/pages/DashboardPage.qml`
- Create: `src/mr_farmboy_manager/qml/pages/SavesPage.qml`
- Modify: `src/mr_farmboy_manager/qml/components/AppShell.qml`
- Modify: `src/mr_farmboy_manager/resources/qml.qrc`
- Regenerate: `src/mr_farmboy_manager/_qml_resources.py`
- Create: `tests/qml/test_dashboard_saves_pages.py`

**Interfaces:**

- Consumes `appController.dashboard` and `appController.saves`.
- Stable names: `dashboardPage`, `dashboardSlotCount`, `savesPage`, `refreshSavesButton`, `saveSlotsList`, `saveDetailsPanel`, `savesErrorMessage`.

- [ ] **Step 1: Write RED page tests**

```python
def test_python_state_reaches_dashboard_and_saves(qml_shell) -> None:
    qml_shell.controller.dashboard.set_fixture_values(slot_count=2, planted=8)
    qml_shell.controller.saves.model_fixture_slots((1, 2))
    qml_shell.process_events()
    assert qml_shell.find("dashboardSlotCount").property("text") == "2"
    assert qml_shell.find("saveSlotsList").property("count") == 2


def test_refresh_button_reaches_python(qml_shell) -> None:
    qml_shell.click("refreshSavesButton")
    assert qml_shell.controller.saves.refresh_calls == 1
```

Also cover loading, empty, error, selected details, missing metrics and width 960.

- [ ] **Step 2: Run RED**

Run the new test file; expected failure is absent pages/object names.

- [ ] **Step 3: Implement both pages**

Dashboard uses responsive grids for slots, backups, last backup, active slot, real crop metrics and growth bars. Saves uses master/detail at 1100 px or wider and vertical stacking below it, `ListView` roles, state-specific loaders and structured metrics. No numeric literal represents user data.

- [ ] **Step 4: Regenerate resources, run GREEN and synchronize**

Run page tests plus Saves/Dashboard ViewModel tests, full pytest and diff checks. Commit `feat(qml): add dashboard and saves pages`, push, fetch and confirm synchronization.

### Task 9: Build the Backups page and confirmation flow

**Files:**

- Create: `src/mr_farmboy_manager/qml/pages/BackupsPage.qml`
- Modify: `src/mr_farmboy_manager/qml/components/AppShell.qml`
- Modify: `src/mr_farmboy_manager/qml/components/ConfirmActionDialog.qml`
- Modify: `src/mr_farmboy_manager/resources/qml.qrc`
- Regenerate: `src/mr_farmboy_manager/_qml_resources.py`
- Create: `tests/qml/test_backups_page.py`

**Interfaces:**

- Consumes `appController.backups`.
- Stable names: `backupsPage`, `backupsList`, `createBackupButton`, `restoreBackupButton`, `deleteBackupButton`, `backupConfirmDialog`.

- [ ] **Step 1: Write RED confirmation tests**

```python
def test_delete_opens_dialog_before_python_confirmation(qml_shell) -> None:
    qml_shell.controller.backups.model_fixture_backup("backup-id")
    qml_shell.controller.backups.selectBackup("backup-id")
    qml_shell.click("deleteBackupButton")
    assert qml_shell.find("backupConfirmDialog").property("visible") is True
    assert qml_shell.controller.backups.confirm_calls == []
```

Prove confirm passes the same action/ID, cancel performs no mutation, delete has `danger` variant, and controls disable during every mutation state.

- [ ] **Step 2: Run RED**

Run the new test file; expected failure is absent page.

- [ ] **Step 3: Implement responsive records and immutable dialog identity**

Use aligned columns at wide widths and cards below 1000 px. When the dialog opens, copy action and backup ID into local properties. Only its confirm button calls `confirmAction(action, backupId)`.

- [ ] **Step 4: Regenerate resources, run GREEN and synchronize**

Run the page test, Backups ViewModel tests, restore/delete domain tests, full pytest and diff checks. Commit `feat(qml): add backup management page`, push, fetch and confirm synchronization.

### Task 10: Build Settings and Diagnostics pages

**Files:**

- Create: `src/mr_farmboy_manager/qml/pages/SettingsPage.qml`
- Create: `src/mr_farmboy_manager/qml/pages/DiagnosticsPage.qml`
- Modify: `src/mr_farmboy_manager/qml/components/AppShell.qml`
- Modify: `src/mr_farmboy_manager/resources/qml.qrc`
- Regenerate: `src/mr_farmboy_manager/_qml_resources.py`
- Create: `tests/qml/test_settings_diagnostics_pages.py`

**Interfaces:**

- Consumes `appController.settings` and `appController.diagnostics`.
- Stable names: `settingsPage`, `saveRootField`, `gameInstallField`, `saveRootBadge`, `gameInstallBadge`, `saveSettingsButton`, `saveRootMessage`, `diagnosticsPage`, `diagnosticsEvents`, `copyDiagnosticButton`, `openLogsButton`.

- [ ] **Step 1: Write RED binding and action tests**

```python
def test_normalized_path_feedback_is_visible(qml_shell) -> None:
    qml_shell.controller.settings.set_fixture_save_root("C:/game_data", "Raiz normalizada para game_data.")
    qml_shell.process_events()
    assert qml_shell.find("saveRootField").property("text") == "C:/game_data"
    assert "normalizada" in qml_shell.find("saveRootMessage").property("text").lower()


def test_diagnostic_buttons_reach_python(qml_shell) -> None:
    qml_shell.click("copyDiagnosticButton")
    qml_shell.click("openLogsButton")
    assert qml_shell.controller.diagnostics.copy_calls == 1
    assert qml_shell.controller.diagnostics.open_calls == 1
```

Also cover valid/invalid/unset badges, dirty save enablement, chooser cancellation, log empty/error and narrow scrolling.

- [ ] **Step 2: Run RED**

Run the new test file; expected failure is absent pages.

- [ ] **Step 3: Implement both pages**

Settings uses three cards, explicit labels, native chooser buttons and text badges. Diagnostics uses a bounded event list with selectable/wrapped text, path labels and compact actions. Each page has one outer `ScrollView` and no absolute structural coordinates.

- [ ] **Step 4: Regenerate resources, run GREEN and synchronize**

Run page and corresponding ViewModel tests, full pytest and diff checks. Commit `feat(qml): add settings and diagnostics pages`, push, fetch and confirm synchronization.

### Task 11: Complete QML integration, E2E and switch the entry point

**Files:**

- Create: `tests/qml/test_qml_bindings.py`
- Create: `tests/test_qml_e2e.py`
- Modify: `tests/test_logging.py`
- Modify: `src/mr_farmboy_manager/qml_application.py`
- Modify: `src/mr_farmboy_manager/__main__.py`
- Modify: `pyproject.toml`
- Modify: `tools/windows_entrypoint.py`

**Interfaces:**

- Changes the console script to `mr_farmboy_manager.qml_application:run`.
- Changes module and Windows entry points to import `qml_application.run`.
- Preserves `MR_FARMBOY_RUNTIME_ROOT`, portable settings, backups and logs.

- [ ] **Step 1: Write RED bidirectional tests**

```python
def test_qml_action_and_python_notify_are_bidirectional(qml_runtime) -> None:
    qml_runtime.click("refreshSavesButton")
    assert qml_runtime.controller.saves.refresh_calls == 1
    qml_runtime.controller.saves.set_fixture_state("error", "Falha segura")
    qml_runtime.process_events()
    assert qml_runtime.find("savesErrorMessage").property("text") == "Falha segura"
```

- [ ] **Step 2: Write the complete temporary-filesystem E2E**

Configure `tmp_path/game_data`, select `save_1`, inspect fixture `.tres`, create a backup under `tmp_path/runtime/backups`, restore after a controlled temporary change, delete it, refresh and assert a sanitized log under `tmp_path/runtime/logs`. Assert no path outside `tmp_path` changed.

- [ ] **Step 3: Run RED**

Run QML bindings and E2E; expected entry-point assertions fail because Widgets is still configured.

- [ ] **Step 4: Wire production dependencies and switch entry points**

`qml_application.run()` creates settings exactly like legacy `run()`, logs engine/controller/load/shutdown events, initializes after the root loads and shuts down the runner before return. Change the three active entry points without deleting `application.py`.

Port the application-run test in `tests/test_logging.py` to patch `qml_application` dependencies and assert `qml.engine.started`, `qml.controller.initialized` and shutdown without starting a real event loop.

```python
from mr_farmboy_manager.qml_application import run
```

- [ ] **Step 5: Run paridade GREEN and synchronize**

Run bindings, new QML E2E, legacy E2E and full pytest offscreen. Commit `feat(qml): switch application entry point`, push, fetch and confirm synchronization.

### Task 12: Package QML resources and smoke-test the Windows artifact

**Files:**

- Modify: `tools/build_windows.py`
- Modify: `tools/smoke_windows_build.py`
- Modify: `tests/test_packaging.py`
- Modify: `src/mr_farmboy_manager/resources/qml.qrc`
- Regenerate: `src/mr_farmboy_manager/_qml_resources.py`

**Interfaces:**

- `build_command()` collects only the Qt QML/Quick modules demonstrated necessary by the build.
- Smoke launches the packaged executable with temporary `MR_FARMBOY_RUNTIME_ROOT`, waits for readiness, verifies embedded resources and terminates cleanly.

- [ ] **Step 1: Write RED packaging tests**

```python
def test_build_collects_qml_runtime_plugins() -> None:
    command = build_command(project_root=Path("C:/project"))
    joined = " ".join(command)
    assert "PySide6.QtQml" in joined
    assert "PySide6.QtQuick" in joined
    assert "PySide6.QtQuickControls2" in joined


def test_windows_entrypoint_delegates_exit_code_to_qml_run(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        mr_farmboy_manager.qml_application,
        "run",
        lambda: calls.append("run") or 23,
    )
    with pytest.raises(SystemExit) as raised:
        runpy.run_path("tools/windows_entrypoint.py", run_name="__main__")
    assert raised.value.code == 23
    assert calls == ["run"]
```

- [ ] **Step 2: Run RED**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_packaging.py -q`

Expected: build command lacks explicit QML runtime collection.

- [ ] **Step 3: Implement narrow PyInstaller collection**

Add `--hidden-import` entries for `PySide6.QtQml`, `PySide6.QtQuick` and `PySide6.QtQuickControls2`. Add plugin/data collection only if the real build identifies a missing plugin; do not blanket-collect all PySide6 unless a reproduced failure proves it necessary and the test documents why.

- [ ] **Step 4: Run build and smoke GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_packaging.py -q
.\.venv\Scripts\python.exe tools\build_windows.py
.\.venv\Scripts\python.exe tools\smoke_windows_build.py
```

Expected: `dist/MR-FARMBOY-Manager/MR-FARMBOY-Manager.exe` loads QML outside the source tree, writes only below a temporary runtime root and exits without modal interaction.

- [ ] **Step 5: Verify, commit and synchronize**

Run full pytest and diff checks. Do not commit `build/` or `dist/`. Commit `build: package qml frontend for windows`, push, fetch and confirm synchronization.

### Task 13: Perform visual QA and responsive polish

**Required workflow:** use the available Windows/computer control skill to inspect the running QML application with temporary fixture data.

**Files:**

- Modify when evidence requires: `src/mr_farmboy_manager/qml/Theme.qml`
- Modify when evidence requires: `src/mr_farmboy_manager/qml/components/*.qml`
- Modify when evidence requires: `src/mr_farmboy_manager/qml/pages/*.qml`
- Create: `tests/qml/test_responsive_layout.py`
- Regenerate: `src/mr_farmboy_manager/_qml_resources.py`
- Create: `docs/qa/2026-08-10-qml-visual-qa.md`

**Interfaces:**

- Produces automated layout invariants and a QA record for 1280×720, 1366×768, 1600×900 and 1920×1080.

- [ ] **Step 1: Add RED invariants for observed defects**

```python
@pytest.mark.parametrize("width,height", [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)])
def test_shell_has_no_negative_geometry(qml_shell, width: int, height: int) -> None:
    qml_shell.resize(width, height)
    qml_shell.process_events()
    for item in qml_shell.named_layout_items():
        assert item.property("width") >= 0
        assert item.property("height") >= 0
```

For every reproduced clipping, overflow or unusable scroll issue, add a focused invariant before its fix. Do not add pixel snapshots.

- [ ] **Step 2: Inspect every page at all target sizes**

Record clipping, overflow, truncation, alignment, spacing, contrast, focus, sidebar mode, scrolling, empty/error states and destructive-action distinction. The QA document records fixture type and corrections, never real save contents.

- [ ] **Step 3: Apply evidence-backed polish**

Keep colors in `Theme.qml`, sizing in layouts and transitions at 120–180 ms. Correct only demonstrated text elision/wrapping, minimum sizes, grid columns, scroll ownership and focus outlines.

- [ ] **Step 4: Run GREEN and synchronize**

Regenerate resources; run all QML tests, QML E2E, build smoke and full pytest; reinspect failed cases. Commit `style(qml): polish responsive desktop experience`, push, fetch and confirm synchronization.

### Task 14: Remove the legacy Qt Widgets frontend

**Files:**

- Delete: `src/mr_farmboy_manager/application.py`
- Delete: `tests/test_application.py`
- Delete: `tests/test_auto_refresh_ui.py`
- Delete: `tests/test_backup_creation_ui.py`
- Delete: `tests/test_backup_delete_ui.py`
- Delete: `tests/test_backup_list_ui.py`
- Delete: `tests/test_backup_restore_ui.py`
- Delete: `tests/test_configuration_refresh_ui.py`
- Delete: `tests/test_default_game_install_directory_dialog_ui.py`
- Delete: `tests/test_default_manual_loader_fallback_ui.py`
- Delete: `tests/test_default_save_directory_dialog_ui.py`
- Delete: `tests/test_first_run_ui.py`
- Delete: `tests/test_game_install_directory_chooser_ui.py`
- Delete: `tests/test_manual_empty_result_ui.py`
- Delete: `tests/test_manual_not_directory_result_ui.py`
- Delete: `tests/test_manual_not_found_result_ui.py`
- Delete: `tests/test_manual_paths_form_ui.py`
- Delete: `tests/test_manual_save_loader_click_ui.py`
- Delete: `tests/test_manual_save_loader_contract_ui.py`
- Delete: `tests/test_manual_valid_render_ui.py`
- Delete: `tests/test_mvp_e2e.py`
- Delete: `tests/test_persistent_paths_ui.py`
- Delete: `tests/test_restored_paths_startup_ui.py`
- Delete: `tests/test_save_details_ui.py`
- Delete: `tests/test_save_directory_chooser_ui.py`
- Delete: `tests/test_save_slots_render_helper_ui.py`
- Delete: `tests/test_save_slots_render_replacement_ui.py`
- Delete: `tests/test_save_slots_ui.py`
- Modify: `tests/conftest.py`
- Modify: `README.md`

**Interfaces:**

- No active production import of `application.py`, `QMainWindow` or other legacy structural widget remains.
- `QFileDialog` is allowed only inside the isolated, injected native chooser adapter.
- Every deleted behavioral test maps to a named ViewModel, QML binding or E2E test.

- [ ] **Step 1: Build a behavior coverage matrix before deletion**

Add a README table mapping configuration, timer, save listing/selection/details, backup create/list/restore/delete, persistence and dialogs to their new test files. If a row lacks coverage, first add a failing test to the named new test file and make it pass.

- [ ] **Step 2: Prove active entry points no longer need Widgets**

Run:

```powershell
rg -n "mr_farmboy_manager\.application|create_main_window|QMainWindow" src tools pyproject.toml
```

Expected before deletion: matches occur only in the legacy module, not active entry points.

- [ ] **Step 3: Delete legacy files and preserve dialog guard**

Remove only the listed files after the coverage matrix passes. Keep centralized read-only local path fixtures and the native file-dialog guard in `tests/conftest.py`.

- [ ] **Step 4: Run removal GREEN and synchronize**

Run full pytest, QML E2E, build and packaged smoke, then repeat `rg`. Inspect all deletions. Commit `refactor(qml): remove legacy widgets frontend`, push, fetch and confirm synchronization.

### Task 15: Final review, release metadata and migration gate

**Files:**

- Modify: `src/mr_farmboy_manager/__init__.py`
- Modify: `pyproject.toml`
- Modify: `packaging/windows_version_info.txt`
- Modify: `tests/test_release_metadata.py`
- Modify: `README.md`

**Interfaces:**

- Sets the validated migration release version to `0.2.0` in every metadata source.
- Does not create, move or overwrite the existing `v0.1.0` tag.

- [ ] **Step 1: Run final code review before version changes**

Invoke `/requesting-code-review`. Review architecture boundaries, QML/Python contracts, filesystem safety, stale-result handling, accessibility, embedded resources, test coverage and removal completeness. Process actionable findings through `/receiving-code-review`; every validated correction receives a failing test, independent commit and push before continuing.

- [ ] **Step 2: Write RED release metadata test**

```python
def test_release_version_is_0_2_0() -> None:
    assert mr_farmboy_manager.__version__ == "0.2.0"
    assert project_version() == "0.2.0"
    assert windows_file_version() == (0, 2, 0, 0)
```

- [ ] **Step 3: Run RED and update exact metadata**

Run `\.venv\Scripts\python.exe -m pytest tests/test_release_metadata.py -q`; expected failure shows `0.1.0`. Change Python, project and Windows metadata to `0.2.0`; update README run/build documentation.

- [ ] **Step 4: Run the complete final gate**

Invoke `/verification-before-completion`, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest tests\qml tests\test_qml_e2e.py -q
.\.venv\Scripts\python.exe tools\build_windows.py
.\.venv\Scripts\python.exe tools\smoke_windows_build.py
git diff --check
git status --short
```

Expected: zero failures, only release files belong to this task, packaged QML smoke passes, and `locais.txt` remains untouched/untracked.

- [ ] **Step 5: Commit, push and prove equality**

```powershell
git add -- src/mr_farmboy_manager/__init__.py pyproject.toml packaging/windows_version_info.txt tests/test_release_metadata.py README.md
git commit -m "chore(release): prepare v0.2.0"
git push origin main
git fetch origin
git status -sb
git rev-parse HEAD
git rev-parse origin/main
```

Expected: both hashes are identical, no ahead/behind, and no migration file remains uncommitted.

- [ ] **Step 6: Close and audit subagents**

Run `/closing-stale-subagents`, require `pending_count = 0`, and record total created, maximum simultaneous active, stale handles found, handles closed and active count at finish.
