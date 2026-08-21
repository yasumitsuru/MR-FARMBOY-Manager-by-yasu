# Farm Analytics Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the QML frontend into an evidence-backed farm management dashboard using a consistent typed snapshot, tested analytics and responsive operational views.

**Architecture:** Extend the safe Godot Variant parser only for typed dictionaries, then convert allowlisted save records into an immutable `FarmSnapshot`. Pure Python analytics derives metrics and alerts with explicit provenance; Qt models format the result once per refresh, and QML only presents/navigates it.

**Tech Stack:** Python 3.12, PySide6 6.5+, Qt Core, Qt QML, Qt Quick, Qt Quick Layouts, Qt Quick Controls 2, pytest 9, PyInstaller 6, Windows.

**Spec:** `docs/superpowers/specs/2026-08-21-farm-analytics-dashboard-design.md`

## Global Constraints

- Work directly on the current `main`; do not create a branch or worktree.
- Before each subagent dispatch, run `/closing-stale-subagents`, confirm `pending_count = 0`, dispatch exactly one economical agent, await it, close it and confirm zero again.
- Use `/test-driven-development` for every behavioral change: focused RED, minimal GREEN, refactor while green.
- Use `/systematic-debugging` before changing code in response to any unexpected failure.
- Request a fresh localized review for each task, validate findings with `/receiving-code-review`, then verify independently.
- Never access `.pytest-round12`; every pytest invocation below uses a unique `build/pytest-analytics-*` base temp and disables the cache provider.
- Never write, rename, restore or delete a real save or any file in the real game installation. All mutable tests use `tmp_path` and synthetic minimal TRES.
- Keep `.understory-project-id`, `locais.txt` and all protected pytest directories untracked and unstaged.
- Preserve the distinction between zero and unavailable. No parser/domain/presentation fallback may turn an absent value into `0`.
- QML does no aggregation, filesystem work or business-rule calculation in JavaScript.
- Use only existing PySide6/Qt Quick modules; add no chart library, GPL-only module, paid dependency, font or game asset.
- Before each commit, run targeted tests, the complete suite, `git diff --check`, inspect the diff and staged paths, and invoke `/verification-before-completion`.
- Commit only the logical task, push `main`, fetch, and confirm `HEAD == origin/main` with ahead/behind `0/0`. Do not amend a published commit.
- Do not change version `0.2.0`, create tag `v0.2.0` or publish a release.

## Verified Starting Point

- Isolated full suite: `654 passed, 9 skipped`.
- Isolated QML/E2E gate: `66 passed`.
- The default pytest temp/cache location is not a valid signal on this machine;
  every planned command uses a fresh ignored `build/pytest-analytics-*` root.

## File Responsibility Map

### Parsing and domain

- `godot_variant.py`: syntax-only support for typed Godot dictionaries; never attaches farm meaning.
- `farm_catalog.py`: immutable audited scene/item/buff mappings and upkeep constants.
- `farm_domain.py`: frozen data contracts, evidence types and immutable collection helpers.
- `farm_snapshot_builder.py`: allowlisted conversion from parsed documents into `FarmSnapshot`.
- `farm_analytics.py`: pure metrics, economy breakdown and alert rules.
- `save_details.py`: stable filesystem read, pair revalidation, parser orchestration and attachment of snapshot/analytics to the existing DTO.

### Presentation

- `presentation/farm_models.py`: QAbstractListModel adapters and stable QML roles.
- `presentation/dashboard_view_model.py`: state plus dashboard/related-page models from the precomputed analytics result.
- `presentation/saves_view_model.py`: selected details remain the single source shared with Dashboard.
- `presentation/growth_states_model.py`: evidence-backed growth labels/descriptions.
- `presentation/formatters.py`: optional integer and currency formatting.
- `presentation/app_controller.py`: atomic propagation of the selected inspection result.

### QML

- `qml/components/SectionHeader.qml`: responsive text/action flow and measured implicit height.
- `qml/components/EvidenceBadge.qml`: visible confirmed/derived/unknown label.
- `qml/components/OperationalTable.qml`: dense ListView header/delegate shell with accessible scrolling.
- `qml/pages/DashboardPage.qml`: managerial overview.
- `qml/pages/CropsPage.qml`, `ResourcesPage.qml`, `PeopleAnimalsPage.qml`, `EconomyPage.qml`: full operational tables.
- `qml/components/AppShell.qml`: grouped navigation and stack entries.
- `qml/Theme.qml`: evidence/status/density tokens.
- `resources/qml.qrc` and `_qml_resources.py`: embedded resources.

### Tests and QA

- `tests/test_godot_variant.py`: typed dictionary grammar and security boundaries.
- `tests/test_farm_domain.py`: immutable contracts/catalog.
- `tests/test_farm_snapshot_builder.py`: fixture → parser → snapshot.
- `tests/test_save_details.py`: stable-read integration and no writes.
- `tests/test_farm_analytics.py`: formulas, availability and alerts.
- `tests/presentation/test_farm_models.py`, `test_dashboard_view_model.py`, `test_app_controller.py`: Qt contracts.
- `tests/qml/fakes.py`: typed deterministic dashboard fixture.
- `tests/qml/test_farm_pages.py`, `test_responsive_layout.py`, `test_dashboard_saves_pages.py`: QML bindings and layout gates.
- `tests/test_qml_e2e.py`: full temporary-filesystem journey through analytics.
- `docs/qa/2026-08-21-farm-analytics-visual-qa.md`: evidence by page and resolution.

---

### Task 1: Parse typed Godot dictionaries safely

**Files:**

- Modify: `src/mr_farmboy_manager/godot_variant.py`
- Modify: `tests/test_godot_variant.py`

**Interfaces:**

- Consumes: existing `parse_godot_variant(text: str) -> GodotVariant`.
- Produces: `Dictionary[K,V]({...})` as `GodotVariant(kind=DICTIONARY, entries=..., name="Dictionary[K,V]")`.
- Preserves: typed arrays, limits, redacted repr and sanitized exceptions.

- [ ] **Step 1: Add focused RED tests for real grammar and boundaries**

```python
def test_typed_dictionary_preserves_integer_entries_and_type() -> None:
    parsed = variant("Dictionary[int, int]({57: 9, 58: 0})")
    assert parsed.kind is GodotVariantKind.DICTIONARY
    assert parsed.name == "Dictionary[int,int]"
    assert [(key.value, value.value) for key, value in parsed.entries] == [
        (57, 9),
        (58, 0),
    ]


def test_typed_dictionary_accepts_qualified_enum_type() -> None:
    parsed = variant("Dictionary[DataTypes.itemID, int]({57: 1})")
    assert parsed.name == "Dictionary[DataTypes.itemID,int]"


@pytest.mark.parametrize(
    "source",
    [
        "Dictionary[int]({1: 2})",
        "Dictionary[int, int](1)",
        "Dictionary[int, int]({1: 2}) trailing",
        "Dictionary[int, int]({1: 2}",
        "Dictionary[int, eval]({1: 2})()",
    ],
)
def test_invalid_typed_dictionary_is_rejected_with_sanitized_error(source: str) -> None:
    with pytest.raises(GodotVariantParseError) as raised:
        variant(source)
    assert source not in str(raised.value)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_godot_variant.py -k "typed_dictionary" --basetemp=build\pytest-analytics-task01-red -p no:cacheprovider
```

Expected: the valid dictionary tests fail because `Dictionary[...]` is rejected or returned as a generic constructor.

- [ ] **Step 3: Generalize the typed-container signature parser**

Implement a depth-bounded parser that accepts identifiers, qualified identifiers and nested `Array[...]`, and splits dictionary key/value types only on a top-level comma. Normalize whitespace in `name`.

```python
def _parse_typed_container_signature(name: str, content: str) -> tuple[str, tuple[str, ...]]:
    expected_count = 1 if name == "Array" else 2 if name == "Dictionary" else 0
    if expected_count == 0:
        raise GodotVariantParseError("Token desconhecido")
    parts = _split_top_level_types(content)
    if len(parts) != expected_count or not all(_is_valid_variant_type(part) for part in parts):
        raise GodotVariantParseError("Token desconhecido")
    normalized = tuple(_normalize_variant_type(part) for part in parts)
    return f"{name}[{','.join(normalized)}]", normalized
```

In `_parse_constructor`, accept `Array` and `Dictionary`. A typed dictionary must contain exactly one dictionary argument; copy its immutable `entries` and attach the normalized name. Reject zero or multiple arguments.

```python
if typed_container == "Dictionary":
    if len(arguments) != 1 or arguments[0].kind is not GodotVariantKind.DICTIONARY:
        raise GodotVariantParseError("Construtor tipado invalido")
    return GodotVariant(
        kind=GodotVariantKind.DICTIONARY,
        entries=arguments[0].entries,
        name=normalized_name,
    )
```

- [ ] **Step 4: Run parser tests and verify GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_godot_variant.py tests\test_godot_tres.py --basetemp=build\pytest-analytics-task01-green -p no:cacheprovider
```

Expected: all parser/TRES tests pass; existing typed-array tests remain green.

- [ ] **Step 5: Run review and full verification gates**

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task01-full -p no:cacheprovider
git diff --check
git status --short
```

- [ ] **Step 6: Commit and synchronize**

```powershell
git add src/mr_farmboy_manager/godot_variant.py tests/test_godot_variant.py
git commit -m "feat(parser): support typed Godot dictionaries"
git push origin main
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

---

### Task 2: Add immutable farm domain contracts and audited catalog

**Files:**

- Create: `src/mr_farmboy_manager/farm_domain.py`
- Create: `src/mr_farmboy_manager/farm_catalog.py`
- Create: `tests/test_farm_domain.py`

**Interfaces:**

- Produces all dataclasses named in design §7, including
  `CumulativeEarnings`, plus `MetricValue`, `EconomyBreakdown`, `FarmAlert` and
  `FarmAnalytics` used by Task 4.
- Produces `freeze_pairs(mapping) -> tuple[tuple[str, object], ...]` and `lookup_pair(pairs, key)`.
- Produces immutable `CROP_SCENES`, `ITEM_LABELS`, `INFRASTRUCTURE_SCENES`, `BUFF_UPKEEP`, `FEEDER_RESTOCK_THRESHOLD = 48`, `BASE_SLOT_COUNT = 2`, `UNLOCK_SLOT_INCREMENT = 2`.

- [ ] **Step 1: Write RED tests for immutability, invariants and catalog identity**

```python
def test_farm_snapshot_copies_mutable_inputs() -> None:
    sources = {"wallet": Provenance(EvidenceStatus.CONFIRMED, "island.inventory.wallet", "direct")}
    unavailable = {"revenue_day": "O save não registra fluxo temporal."}
    snapshot = minimal_snapshot(provenance=sources, unavailable_reasons=unavailable)
    sources.clear()
    unavailable.clear()
    assert lookup_pair(snapshot.provenance, "wallet").status is EvidenceStatus.CONFIRMED
    assert lookup_pair(snapshot.unavailable_reasons, "revenue_day") != ""


@pytest.mark.parametrize(("occupied", "capacity"), [(-1, 2), (1, -1), (3, 2)])
def test_capacity_rejects_impossible_values(occupied: int, capacity: int) -> None:
    with pytest.raises(ValueError, match="capacidade inválida"):
        CapacitySnapshot(occupied=occupied, capacity=capacity)


def test_catalog_is_immutable_and_contains_audited_ids() -> None:
    assert ITEM_LABELS[57] == "Cobre"
    assert ITEM_LABELS[348] == "Rancheiro 2"
    assert CROP_SCENES["res://scenes/objects/crops/crops/turnip_crop.tscn"].label == "Nabo"
    with pytest.raises(TypeError):
        ITEM_LABELS[57] = "alterado"
```

- [ ] **Step 2: Run RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_farm_domain.py --basetemp=build\pytest-analytics-task02-red -p no:cacheprovider
```

Expected: collection fails because the modules do not exist.

- [ ] **Step 3: Implement frozen contracts with defensive tuple conversion**

Use `@dataclass(frozen=True, slots=True)` and convert every externally supplied collection in `__post_init__` with `object.__setattr__`.

```python
@dataclass(frozen=True, slots=True)
class CapacitySnapshot:
    occupied: int
    capacity: int

    def __post_init__(self) -> None:
        if type(self.occupied) is not int or type(self.capacity) is not int:
            raise ValueError("capacidade inválida")
        if self.occupied < 0 or self.capacity < 0 or self.occupied > self.capacity:
            raise ValueError("capacidade inválida")

    @property
    def open_slots(self) -> int:
        return self.capacity - self.occupied


def freeze_pairs(values: Mapping[str, T]) -> tuple[tuple[str, T], ...]:
    return tuple(sorted(((str(key), value) for key, value in dict(values).items()), key=lambda row: row[0]))
```

Define concrete fields for `FeederSnapshot`, `WarehouseSnapshot`, `MarketSnapshot` and `ActiveBuffSnapshot` exactly as design §7 specifies. `FarmSnapshot.__post_init__` copies every sequence to tuple and every mapping through `freeze_pairs`.

- [ ] **Step 4: Implement the audited catalog without mutable public dictionaries**

Store internal dict literals and expose `MappingProxyType`. Include all crop scene paths listed in the schema, infrastructure suffixes, item IDs for currencies/resources/animals/workers/feed, and these buff rules:

```python
BUFF_UPKEEP = MappingProxyType(
    {
        2: BuffUpkeep("Ferreiro: fazendeiro II", 2000, "copper"),
        5: BuffUpkeep("Ferreiro: coletor II", 2000, "copper"),
        69: BuffUpkeep("Estábulo: velocidade do cavalo", 0, None),
        79: BuffUpkeep("Estábulo: ferramentas VII", 0, None),
    }
)
```

Unknown IDs are never inserted into the catalog at runtime; adapters create `Item <id>` with `UNKNOWN` evidence.

- [ ] **Step 5: Run domain tests and full verification**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_farm_domain.py --basetemp=build\pytest-analytics-task02-green -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task02-full -p no:cacheprovider
git diff --check
```

- [ ] **Step 6: Commit and synchronize**

```powershell
git add src/mr_farmboy_manager/farm_domain.py src/mr_farmboy_manager/farm_catalog.py tests/test_farm_domain.py
git commit -m "feat(analytics): add immutable farm domain catalog"
git push origin main
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

---

### Task 3: Build one farm snapshot during stable save inspection

**Files:**

- Create: `src/mr_farmboy_manager/farm_snapshot_builder.py`
- Create: `tests/test_farm_snapshot_builder.py`
- Create: `tests/fixtures/farm_analytics_game_data/save_1/player_data.tres`
- Create: `tests/fixtures/farm_analytics_game_data/save_1/island_main_data.tres`
- Modify: `src/mr_farmboy_manager/save_details.py`
- Modify: `tests/test_save_details.py`

**Interfaces:**

- Produces `build_farm_snapshot(*, slot_id: str, player_document: GodotTresDocument | None, island_document: GodotTresDocument | None, captured_at: datetime, save_fingerprint: str) -> FarmSnapshot`.
- Extends `SaveSlotDetails` with trailing default field `farm_snapshot: FarmSnapshot | None = None`, preserving existing positional callers.
- `inspect_save_slot()` builds the snapshot from documents already read in that invocation and never reopens files for analytics.

- [ ] **Step 1: Write RED adapter tests using minimal synthetic TRES**

```python
def test_builder_maps_wallet_crops_workers_animals_and_mode() -> None:
    player = parse_godot_tres_document(
        (HEADER + PLAYER_SECTION_WITH_MODE_AND_COZY).encode("utf-8")
    )
    island = parse_godot_tres_document(
        (HEADER + MINIMAL_FARM_SECTIONS).encode("utf-8")
    )
    snapshot = build_farm_snapshot(
        slot_id="save_1",
        player_document=player,
        island_document=island,
        captured_at=datetime(2026, 8, 21, tzinfo=UTC),
        save_fingerprint="fixture",
    )
    assert snapshot.game_mode == 2
    assert snapshot.cozy_option_2 is False
    assert snapshot.wallet == MoneyBalance(copper=1200, silver=4, gold=0)
    assert snapshot.cumulative_earnings == CumulativeEarnings(
        copper=9000,
        silver=40,
        gold=3,
        provenance=confirmed("player.adv_data.earned"),
    )
    assert snapshot.crops[0].harvestable == 1
    assert snapshot.animals[0].count == 2
    assert snapshot.workers[0].count == 1
```

The two tracked fixture files must contain `Dictionary[int,int]` inventory, one crop scene, one
House, one Coop, one Warehouse and player advanced-data entries for group 11.
Add separate tests for missing key versus persisted zero, unknown ID, missing
player document, `occupied > capacity`, feeder without food, a non-`EARNED`
advanced-data group that must be ignored and deterministic ordering.

- [ ] **Step 2: Run RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_farm_snapshot_builder.py --basetemp=build\pytest-analytics-task03-red -p no:cacheprovider
```

Expected: import fails because the builder does not exist.

- [ ] **Step 3: Implement allowlisted extraction helpers and the O(n) builder**

Use exact scalar helpers and reject booleans as integers. Identify the direct
wallet only when `node_name == "IslandInventory"`; identify scenes only by
catalog entries/suffixes. Extract cumulative earnings only from
`AdvDataID.EARNED` (group 11), allowlisting currency IDs 57/58/59; never merge
other advanced-data groups or inventories into it. Aggregate crops by confirmed
scene, but preserve an unknown crop scene with safe label and unknown evidence.

```python
def _int_dictionary(value: GodotVariant | None) -> tuple[tuple[int, int], ...] | None:
    if value is None or value.kind is not GodotVariantKind.DICTIONARY:
        return None
    rows: list[tuple[int, int]] = []
    for key, item in value.entries:
        if key.kind is not GodotVariantKind.INTEGER or item.kind is not GodotVariantKind.INTEGER:
            return None
        if type(key.value) is not int or type(item.value) is not int:
            return None
        rows.append((key.value, item.value))
    return tuple(rows)
```

Calculate capacity per building as `2 + 2 * true_unlocks`. If any group has negative quantities or `occupied > capacity`, omit that group's `CapacitySnapshot`, add a sanitized unavailable reason and continue with independent data.

- [ ] **Step 4: Integrate documents and fingerprint into `inspect_save_slot`**

Keep parsed target documents and their stable bytes only until the DTO is built. Compute a path-free SHA-256 over exact target filename plus bytes. After both reads, re-`lstat` every successfully read target and compare identity/size/mtime to its pre-open state; discard a target that changed before snapshot construction.

```python
fingerprint = hashlib.sha256()
fingerprint.update(filename.encode("ascii"))
fingerprint.update(read_result.data)
documents[filename] = document
```

No repr includes raw records, node names, IDs from unknown properties or paths.

- [ ] **Step 5: Run focused integration and no-write tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_farm_snapshot_builder.py tests\test_save_details.py --basetemp=build\pytest-analytics-task03-green -p no:cacheprovider
```

Expected: all pass, including hash/mtime preservation and pair-change rejection.

- [ ] **Step 6: Review, full suite, commit and sync**

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task03-full -p no:cacheprovider
git diff --check
git add src/mr_farmboy_manager/farm_snapshot_builder.py src/mr_farmboy_manager/save_details.py tests/test_farm_snapshot_builder.py tests/test_save_details.py tests/fixtures/farm_analytics_game_data/save_1/player_data.tres tests/fixtures/farm_analytics_game_data/save_1/island_main_data.tres
git commit -m "feat(analytics): build farm snapshot from stable saves"
git push origin main
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

---

### Task 4: Derive evidence-backed metrics and alerts

**Files:**

- Create: `src/mr_farmboy_manager/farm_analytics.py`
- Create: `tests/test_farm_analytics.py`
- Modify: `src/mr_farmboy_manager/save_details.py`
- Modify: `tests/test_save_details.py`

**Interfaces:**

- Produces `build_farm_analytics(snapshot: FarmSnapshot | None) -> FarmAnalytics`.
- Extends `SaveSlotDetails` with trailing `farm_analytics: FarmAnalytics | None = None` after `farm_snapshot`.
- The background `inspect_save_slot` call computes analytics once after a snapshot is built.

- [ ] **Step 1: Write RED tests for availability, formulas and boundaries**

```python
def test_real_shape_nominal_upkeep_is_5958_copper_per_day() -> None:
    analytics = build_farm_analytics(snapshot_with_audited_totals())
    assert analytics.nominal_upkeep is not None
    assert analytics.nominal_upkeep.copper_per_day == 5958
    assert analytics.nominal_upkeep.silver_per_day == 0
    assert analytics.nominal_upkeep.gold_per_day == 0
    assert [row.amount for row in analytics.nominal_upkeep.components] == [
        1840,
        52,
        33,
        33,
        4000,
    ]


def test_unknown_revenue_and_balance_never_become_zero() -> None:
    analytics = build_farm_analytics(minimal_snapshot())
    by_id = {metric.metric_id: metric for metric in analytics.unavailable_metrics}
    assert by_id["economy.revenue_day"].value is None
    assert by_id["economy.balance_day"].value is None
    assert by_id["economy.revenue_day"].availability == "unavailable"


def test_capacity_full_alert_requires_exact_valid_boundary() -> None:
    full = build_farm_analytics(snapshot_with_animal_capacity(52, 52))
    open_ = build_farm_analytics(snapshot_with_animal_capacity(51, 52))
    assert "animals.capacity.full" in {alert.alert_id for alert in full.alerts}
    assert "animals.capacity.full" not in {alert.alert_id for alert in open_.alerts}
```

Also test Cozy `true` yields confirmed charged upkeep zero, Cozy unknown yields
unavailable, 47 versus 48 feeder threshold, reserve -1/equal/above, invalid
capacity absence, alert severity/reason/source and that cumulative `EARNED`
values never populate revenue/day, balance/day or any other `/day` metric.

- [ ] **Step 2: Run RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_farm_analytics.py --basetemp=build\pytest-analytics-task04-red -p no:cacheprovider
```

- [ ] **Step 3: Implement pure analytics without Qt or filesystem imports**

```python
def build_farm_analytics(snapshot: FarmSnapshot | None) -> FarmAnalytics:
    if snapshot is None:
        return unavailable_farm_analytics("Nenhum snapshot disponível.")
    kpis = _build_kpis(snapshot)
    upkeep = _build_nominal_upkeep(snapshot)
    alerts = tuple(sorted(_build_alerts(snapshot), key=_alert_sort_key))
    return FarmAnalytics(
        kpis=kpis,
        alerts=alerts,
        crop_totals=_crop_totals(snapshot.crops),
        nominal_upkeep=upkeep,
        unavailable_metrics=_unavailable_flow_metrics(),
    )
```

The expense breakdown sums workers at 10 copper each, adult animals at 1,
distinct Warehouse/Market slots at 1 and confirmed buff costs. It does not count
Horse Stable buffs as paid upkeep. Every output metric carries `Provenance`.

- [ ] **Step 4: Attach analytics in the existing background inspection**

After the builder returns, call `build_farm_analytics` before creating
`SaveSlotDetails`. A partial snapshot yields partial analytics; a missing
snapshot leaves `farm_analytics=None`.

- [ ] **Step 5: Run focused and full suites**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_farm_analytics.py tests\test_save_details.py --basetemp=build\pytest-analytics-task04-green -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task04-full -p no:cacheprovider
git diff --check
```

- [ ] **Step 6: Commit and synchronize**

```powershell
git add src/mr_farmboy_manager/farm_analytics.py src/mr_farmboy_manager/save_details.py tests/test_farm_analytics.py tests/test_save_details.py
git commit -m "feat(analytics): derive farm metrics and alerts"
git push origin main
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

---

### Task 5: Expose analytics through Qt models and ViewModels

**Files:**

- Create: `src/mr_farmboy_manager/presentation/farm_models.py`
- Create: `tests/presentation/test_farm_models.py`
- Modify: `src/mr_farmboy_manager/presentation/formatters.py`
- Modify: `src/mr_farmboy_manager/presentation/growth_states_model.py`
- Modify: `src/mr_farmboy_manager/presentation/dashboard_view_model.py`
- Modify: `src/mr_farmboy_manager/presentation/saves_view_model.py`
- Modify: `src/mr_farmboy_manager/presentation/app_controller.py`
- Modify: `tests/presentation/test_models.py`
- Modify: `tests/presentation/test_dashboard_view_model.py`
- Modify: `tests/presentation/test_saves_view_model.py`
- Modify: `tests/presentation/test_app_controller.py`

**Interfaces:**

- Produces `MetricsModel`, `FarmAlertsModel`, `CropsModel`, `StockModel`,
  `AnimalsModel`, `WorkersModel`, `InfrastructureModel`,
  `EconomyBreakdownModel` and `CumulativeEarningsModel` with roles from design
  §9.1.
- `DashboardViewModel` exposes four separate immutable stock models:
  `directStockModel`, `warehouseStockModel`, `marketStockModel` and
  `feedStockModel`; QML selects a model and never filters rows itself.
- Produces `format_optional_integer(value: int | None) -> str` and `format_currency(value: int | None, currency: str) -> str`.
- `DashboardViewModel.update(...)` consumes the existing `SaveSlotDetails`; it never rereads or recomputes analytics.

- [ ] **Step 1: Write RED model and ViewModel contract tests**

```python
def test_metrics_model_preserves_unavailable_instead_of_zero() -> None:
    model = MetricsModel()
    model.replace((unavailable_metric("economy.revenue_day", "Receita/dia"),))
    index = model.index(0, 0)
    assert model.data(index, MetricsModel.ValueLabelRole) == "—"
    assert model.data(index, MetricsModel.AvailabilityRole) == "unavailable"
    assert model.data(index, MetricsModel.EvidenceLabelRole) == "Indisponível"


def test_dashboard_uses_precomputed_details_analytics() -> None:
    vm = DashboardViewModel()
    details = details_with_analytics(audited_fixture_analytics())
    vm.update(1, details, (), "valid", datetime(2026, 8, 21, tzinfo=UTC))
    assert vm.state == "ready"
    assert vm.kpisModel.rowCount() == 4
    assert vm.alertsModel.rowCount() == 3
    assert vm.hasUnavailableMetrics is True
    assert vm.cumulativeEarningsModel.rowCount() == 3

    for model, expected_origin in (
        (vm.directStockModel, "Inventário direto"),
        (vm.warehouseStockModel, "Armazém"),
        (vm.marketStockModel, "Mercado"),
        (vm.feedStockModel, "Ração"),
    ):
        assert model.rowCount() > 0
        assert {
            model.data(model.index(row, 0), StockModel.OriginLabelRole)
            for row in range(model.rowCount())
        } == {expected_origin}
```

Add tests for every role name, deterministic row order, reset to empty, partial
state, stale details replacement, unknown item label, a missing origin producing
an empty model, accumulated-earnings labels containing no `/dia`, and `changed`
emitted only after all models contain the same snapshot.

- [ ] **Step 2: Run RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\presentation\test_farm_models.py tests\presentation\test_dashboard_view_model.py tests\presentation\test_models.py --basetemp=build\pytest-analytics-task05-red -p no:cacheprovider
```

- [ ] **Step 3: Implement stable row models and optional formatting**

Use one private reset-model base that stores tuples of role dictionaries; each public model owns fixed integer roles and byte role names.

```python
def format_optional_integer(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}".replace(",", ".")
```

Do not expose `Path`, domain objects or dicts as public roles. Use sanitized
strings and primitives only.

- [ ] **Step 4: Make growth labels semantic and honest**

Add `DescriptionRole` and this fixed catalog:

```python
_GROWTH_LABELS = {
    0: ("0–<25% / reinício", "Também pode representar lote resetado ou não plantado."),
    1: ("25–<50%", "Segundo quarto do ciclo cronometrado."),
    2: ("50–<75%", "Terceiro quarto do ciclo cronometrado."),
    3: ("≥75% / colhível", "O jogo marca o lote como colhível neste estágio."),
}
```

Unknown states render `Estado <n> (não reconhecido)` and an unknown-evidence description.

- [ ] **Step 5: Replace dashboard state atomically**

Populate all list models before emitting the single `changed` signal. Partition
the snapshot stock exactly once in Python into the four origin-specific
`StockModel` instances; expose `cumulativeEarningsModel` directly from
`FarmSnapshot.cumulative_earnings`, labeled as accumulated history. Keep the old
scalar properties temporarily for Saves/E2E compatibility, but source them from
the same snapshot and add availability booleans rather than zero fallbacks.
`AppController` continues to pass only `_loaded_details`; no second loader is
introduced.

- [ ] **Step 6: Run focused and full suites**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\presentation --basetemp=build\pytest-analytics-task05-green -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task05-full -p no:cacheprovider
git diff --check
```

- [ ] **Step 7: Commit and synchronize**

```powershell
git add src/mr_farmboy_manager/presentation/farm_models.py src/mr_farmboy_manager/presentation/formatters.py src/mr_farmboy_manager/presentation/growth_states_model.py src/mr_farmboy_manager/presentation/dashboard_view_model.py src/mr_farmboy_manager/presentation/saves_view_model.py src/mr_farmboy_manager/presentation/app_controller.py tests/presentation/test_farm_models.py tests/presentation/test_models.py tests/presentation/test_dashboard_view_model.py tests/presentation/test_saves_view_model.py tests/presentation/test_app_controller.py
git commit -m "feat(presentation): expose farm analytics models"
git push origin main
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

---

### Task 6: Build the managerial QML dashboard and related pages

**Files:**

- Create: `src/mr_farmboy_manager/qml/components/EvidenceBadge.qml`
- Create: `src/mr_farmboy_manager/qml/components/OperationalTable.qml`
- Create: `src/mr_farmboy_manager/qml/pages/CropsPage.qml`
- Create: `src/mr_farmboy_manager/qml/pages/ResourcesPage.qml`
- Create: `src/mr_farmboy_manager/qml/pages/PeopleAnimalsPage.qml`
- Create: `src/mr_farmboy_manager/qml/pages/EconomyPage.qml`
- Create: `tests/qml/test_farm_pages.py`
- Modify: `src/mr_farmboy_manager/qml/pages/DashboardPage.qml`
- Modify: `src/mr_farmboy_manager/qml/components/AppShell.qml`
- Modify: `src/mr_farmboy_manager/qml/Theme.qml`
- Modify: `src/mr_farmboy_manager/resources/qml.qrc`
- Regenerate: `src/mr_farmboy_manager/_qml_resources.py`
- Modify: `tests/qml/fakes.py`
- Modify: `tests/qml/test_backups_page.py`
- Modify: `tests/qml/test_dashboard_saves_pages.py`
- Modify: `tests/qml/test_qml_bindings.py`
- Modify: `tests/qml/test_qml_bootstrap.py`
- Modify: `tests/qml/test_responsive_layout.py`
- Modify: `tests/qml/test_settings_diagnostics_pages.py`
- Modify: `tests/test_qml_e2e.py`

**Interfaces:**

- Consumes the model properties from Task 5 only.
- Exposes stable object names: `dashboardKpis`, `dashboardAlerts`,
  `dashboardUnavailable`, `cropsTable`, `resourcesOriginSelector`,
  `resourcesTable`, `animalsTable`, `workersTable`, `economyBreakdown`,
  `cumulativeEarnings` and `infrastructureTable`.
- Navigation order: Overview 0, Crops 1, Resources 2, People/Animals 3, Economy 4, Saves 5, Backups 6, Settings 7, Diagnostics 8.

- [ ] **Step 1: Extend QML fakes and write RED binding tests**

```python
def test_dashboard_renders_wallet_alert_and_unavailable_rate(qapp, qml_shell, fake_controller) -> None:
    fake_controller.dashboard.set_analytics_fixture()
    qapp.processEvents()
    assert _find(qml_shell, "dashboardKpis").property("count") == 4
    assert _find(qml_shell, "dashboardAlerts").property("count") == 3
    assert _find(qml_shell, "dashboardUnavailable").property("visible") is True


@pytest.mark.parametrize(
    ("page_index", "object_name"),
    [(1, "cropsTable"), (2, "resourcesTable"), (3, "animalsTable"), (4, "economyBreakdown")],
)
def test_managerial_pages_receive_typed_models(qapp, qml_shell, page_index: int, object_name: str) -> None:
    _find(qml_shell, "appShell").setProperty("currentIndex", page_index)
    fake_controller.dashboard.set_analytics_fixture()
    qapp.processEvents()
    assert _find(qml_shell, object_name).property("visible") is True
```

Add an assertion that the text for unavailable revenue is `—` or
`Indisponível`, never `0`, and an integrated temporary fixture that reaches a
crop row and animal row through parser → analytics → ViewModel → QML. Add a
resources-page test that changes `resourcesOriginSelector` through all four
indices and proves `resourcesTable.model` becomes, respectively,
`directStockModel`, `warehouseStockModel`, `marketStockModel` and
`feedStockModel`, without a JavaScript filter. Assert the Economy page renders
`cumulativeEarnings` as "Acumulado histórico" and never includes `/dia` in
those rows.

- [ ] **Step 2: Run RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\qml\test_farm_pages.py tests\qml\test_dashboard_saves_pages.py tests\test_qml_e2e.py --basetemp=build\pytest-analytics-task06-red -p no:cacheprovider
```

- [ ] **Step 3: Add evidence and dense-table components**

`EvidenceBadge` maps only `confirmed`, `derived`, `inferred`, `unknown` and
`unavailable` to fixed text/tokens. `OperationalTable` owns a clipped ListView,
header, empty text, accessible name and scroll behavior; delegates remain
page-specific so each table uses meaningful columns.

- [ ] **Step 4: Rebuild Dashboard with the field-ledger hierarchy**

Use `ScrollView` + `ColumnLayout`: header, compact KPI grid, alerts, unavailable
explanation, economy, crop preview, resources, people/animals and infrastructure.
The four primary KPIs are wallet, nominal cost/day, harvestable and animal
capacity. Bind values/labels directly from roles. Use no JavaScript sum/filter.

- [ ] **Step 5: Add full related pages and nine-entry navigation**

Implement the exact columns in design §12. Keep previews to at most eight rows;
full models belong to pages. For compact navigation, Drawer shows all nine
entries; rail/wide navigation may group the five managerial entries under a
visual label while preserving direct keyboard access.

On Resources, the origin control only selects one of the four prefiltered model
properties from Task 5; it does not run `filter()`, construct arrays or inspect
row contents in QML. On Economy, render wallet, accumulated `EARNED` and
unavailable flow rates as three visibly separate concepts.

Update every existing navigation test/call site to the normative indices in the
Interfaces block. Saves moves from 1 to 5, Backups from 2 to 6, Settings from 3
to 7 and Diagnostics from 4 to 8. Dashboard actions that open Saves or Settings
must use 5 or 7. The full suite must contain no stale numeric navigation index.

- [ ] **Step 6: Embed resources and regenerate the registry**

```powershell
.\.venv\Scripts\pyside6-rcc.exe src\mr_farmboy_manager\resources\qml.qrc -o src\mr_farmboy_manager\_qml_resources.py
```

- [ ] **Step 7: Run focused and full suites**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\qml tests\test_qml_e2e.py --basetemp=build\pytest-analytics-task06-green -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task06-full -p no:cacheprovider
git diff --check
```

- [ ] **Step 8: Commit and synchronize**

```powershell
git add src/mr_farmboy_manager/qml/components/EvidenceBadge.qml src/mr_farmboy_manager/qml/components/OperationalTable.qml src/mr_farmboy_manager/qml/pages/DashboardPage.qml src/mr_farmboy_manager/qml/pages/CropsPage.qml src/mr_farmboy_manager/qml/pages/ResourcesPage.qml src/mr_farmboy_manager/qml/pages/PeopleAnimalsPage.qml src/mr_farmboy_manager/qml/pages/EconomyPage.qml src/mr_farmboy_manager/qml/components/AppShell.qml src/mr_farmboy_manager/qml/Theme.qml src/mr_farmboy_manager/resources/qml.qrc src/mr_farmboy_manager/_qml_resources.py tests/qml/fakes.py tests/qml/test_farm_pages.py tests/qml/test_backups_page.py tests/qml/test_dashboard_saves_pages.py tests/qml/test_qml_bindings.py tests/qml/test_qml_bootstrap.py tests/qml/test_responsive_layout.py tests/qml/test_settings_diagnostics_pages.py tests/test_qml_e2e.py
git commit -m "feat(qml): add managerial farm views"
git push origin main
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

---

### Task 7: Fix responsive headers and critical overlaps structurally

**Files:**

- Modify: `src/mr_farmboy_manager/qml/components/SectionHeader.qml`
- Modify: `src/mr_farmboy_manager/qml/pages/DashboardPage.qml`
- Modify: `src/mr_farmboy_manager/qml/pages/SavesPage.qml`
- Modify: `src/mr_farmboy_manager/resources/qml.qrc`
- Regenerate: `src/mr_farmboy_manager/_qml_resources.py`
- Modify: `tests/qml/test_responsive_layout.py`
- Modify: `tests/qml/test_dashboard_saves_pages.py`

**Interfaces:**

- `SectionHeader` retains `title`, `subtitle` and the exact
  `default property alias action: actionSlot.data` contract for declarative
  child actions.
- Adds `compactBreakpoint: int = 560` and stable names `<objectName>Title`, `<objectName>Subtitle`, `<objectName>Action`, `<objectName>Layout`.
- Its `implicitHeight` always contains title, subtitle and action.

- [ ] **Step 1: Write RED geometry tests for the two reported bugs**

```python
@pytest.mark.parametrize(("width", "height"), ((960, 640), (1280, 720), (1366, 768)))
def test_headers_do_not_overlap_text_action_or_following_content(qapp, qml_shell, width: int, height: int) -> None:
    qml_shell.setWidth(width)
    qml_shell.setHeight(height)
    for page_index, header_name, following_name in (
        (0, "dashboardHeader", "dashboardKpis"),
        (5, "savesLedgerHeader", "savesLedgerDivider"),
    ):
        _find(qml_shell, "appShell").setProperty("currentIndex", page_index)
        qapp.processEvents()
        header = _find(qml_shell, header_name)
        for left, right in (
            (header_name + "Title", header_name + "Action"),
            (header_name + "Subtitle", header_name + "Action"),
            (header_name, following_name),
        ):
            assert not _intersects(_find(qml_shell, left), _find(qml_shell, right), qml_shell)
```

Add a test that title/subtitle have positive implicit height, a declarative
child action is parented through `actionSlot.data`, contributes to the header's
implicit height and wraps below text at compact component width.

- [ ] **Step 2: Run RED and capture the current overlap**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\qml\test_responsive_layout.py -k "headers_do_not_overlap" --basetemp=build\pytest-analytics-task07-red -p no:cacheprovider
```

Expected: at least the Saves action or Dashboard configuration badge intersects text/following content.

- [ ] **Step 3: Replace the one-row header with a measured GridLayout**

```qml
default property alias action: actionSlot.data
implicitHeight: headerLayout.implicitHeight
GridLayout {
    id: headerLayout
    objectName: header.objectName.length > 0 ? header.objectName + "Layout" : ""
    anchors.fill: parent
    columns: header.width < header.compactBreakpoint ? 1 : 2
    columnSpacing: AppTheme.Theme.space16
    rowSpacing: AppTheme.Theme.space8
    ColumnLayout {
        Layout.fillWidth: true
        Text { objectName: header.objectName + "Title"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Text { objectName: header.objectName + "Subtitle"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    }
    Item {
        id: actionSlot
        Layout.fillWidth: headerLayout.columns === 1
        Layout.alignment: headerLayout.columns === 1 ? Qt.AlignLeft : Qt.AlignRight
        implicitWidth: childrenRect.width
        implicitHeight: childrenRect.height
    }
}
```

Do not give Layout-managed children anchors. Give the Saves divider and
Dashboard KPI area stable object names so tests compare actual following
content. The configuration badge stays in the header action flow.

- [ ] **Step 4: Regenerate resources and run responsive tests**

```powershell
.\.venv\Scripts\pyside6-rcc.exe src\mr_farmboy_manager\resources\qml.qrc -o src\mr_farmboy_manager\_qml_resources.py
.\.venv\Scripts\python.exe -m pytest tests\qml\test_responsive_layout.py tests\qml\test_dashboard_saves_pages.py --basetemp=build\pytest-analytics-task07-green -p no:cacheprovider
```

- [ ] **Step 5: Run full suite, commit and sync**

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task07-full -p no:cacheprovider
git diff --check
git add src/mr_farmboy_manager/qml/components/SectionHeader.qml src/mr_farmboy_manager/qml/pages/DashboardPage.qml src/mr_farmboy_manager/qml/pages/SavesPage.qml src/mr_farmboy_manager/resources/qml.qrc src/mr_farmboy_manager/_qml_resources.py tests/qml/test_responsive_layout.py tests/qml/test_dashboard_saves_pages.py
git commit -m "fix(qml): prevent responsive header overlaps"
git push origin main
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

---

### Task 8: Complete responsive and visual QA evidence

**Files:**

- Modify: `tests/qml/test_responsive_layout.py`
- Modify: `tests/qml/test_farm_pages.py`
- Create: `docs/qa/2026-08-21-farm-analytics-visual-qa.md`

**Interfaces:**

- Expands `SIZES` to `((960, 640), (1280, 720), (1366, 768), (1600, 900), (1920, 1080))`.
- The QA report records each resolution/page, checked items, initial issue, correction and final result.

- [ ] **Step 1: Add RED coverage for every page at every required size**

```python
SIZES = ((960, 640), (1280, 720), (1366, 768), (1600, 900), (1920, 1080))


@pytest.mark.parametrize(("width", "height"), SIZES)
@pytest.mark.parametrize(
    ("page_index", "required_names"),
    (
        (0, ("dashboardKpis", "dashboardAlerts")),
        (1, ("cropsTable",)),
        (2, ("resourcesTable",)),
        (3, ("animalsTable", "workersTable")),
        (4, ("economyBreakdown", "infrastructureTable")),
        (5, ("savesLedgerHeader", "saveDetailsPanel")),
        (6, ("backupsList",)),
        (7, ("saveRootField",)),
        (8, ("diagnosticsEvents",)),
    ),
)
def test_all_pages_have_valid_reachable_geometry(qapp, qml_shell, width, height, page_index, required_names) -> None:
    qml_shell.setWidth(width)
    qml_shell.setHeight(height)
    _find(qml_shell, "appShell").setProperty("currentIndex", page_index)
    qapp.processEvents()
    for name in required_names:
        _assert_valid_geometry(_find(qml_shell, name))
```

Also verify positive table viewport sizes, horizontal/vertical scroll reach,
sidebar/drawer selection, no card intersection, elided text has Accessible name,
and no QML warning for all pages.

- [ ] **Step 2: Run responsive tests and use systematic debugging for failures**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\qml\test_responsive_layout.py tests\qml\test_farm_pages.py --basetemp=build\pytest-analytics-task08-red -p no:cacheprovider
```

Expected: any missing object name, invalid geometry or unreachable table fails
with the exact page/size. Fix only demonstrated layout causes in the responsible
QML file, regenerate resources, and rerun the failing node before the whole pair.

- [ ] **Step 3: Perform visual inspection and record evidence**

At each required size, inspect Dashboard, Saves and one dense table page. Capture
screenshots under `build/qml-qa/2026-08-21/<width>x<height>/`; do not commit image
files. The report table must use the exact columns `Resolução`, `Página`,
`Verificado`, `Problemas iniciais`, `Correção` and `Resultado`. Write each row
only after that page/size is inspected, using observed facts and the final
command result.

Record separate rows for `Atualizar` and `Configuração ativa`. Do not write
“looks good”; state geometry/content observations.

- [ ] **Step 4: Run QML/E2E and full verification**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\qml tests\test_qml_e2e.py --basetemp=build\pytest-analytics-task08-qml -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task08-full -p no:cacheprovider
git diff --check
```

- [ ] **Step 5: Commit QA tests/report and synchronize**

```powershell
git add tests/qml/test_responsive_layout.py tests/qml/test_farm_pages.py docs/qa/2026-08-21-farm-analytics-visual-qa.md
git commit -m "test(qml): verify farm dashboard responsiveness"
git push origin main
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

If visual fixes changed QML during this task, stage the exact affected QML and
regenerated resource file in the same commit, and list those corrections in the
QA report.

---

### Task 9: Final suite, Windows build, isolated smokes and packaged journey

**Files:**

- Verify only: repository, generated Windows artifact and ignored evidence under
  `build/packaged-ui-smoke-20260821/`.
- Modify only if a demonstrated build/smoke failure requires a separate tested fix commit.

**Interfaces:**

- Produces fresh verification evidence and `dist/MR-FARMBOY-Manager/MR-FARMBOY-Manager.exe`.
- Proves startup twice automatically and the visible packaged journey once with
  the tracked synthetic analytics fixture.
- Does not create a Git tag or release.

- [ ] **Step 1: Confirm clean synchronization and protected local files**

```powershell
git fetch origin
git status -sb
git rev-parse HEAD
git rev-parse origin/main
git rev-list --left-right --count HEAD...origin/main
Test-Path -LiteralPath '.pytest-round12'
Test-Path -LiteralPath '.understory-project-id'
Test-Path -LiteralPath 'locais.txt'
```

Expected: main synchronized at `0 0`; protected paths present and untracked.

- [ ] **Step 2: Run final automated gates with a fresh base temp**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\qml tests\test_qml_e2e.py --basetemp=build\pytest-analytics-task09-qml -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py tests\test_packaging.py --basetemp=build\pytest-analytics-task09-release -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest --basetemp=build\pytest-analytics-task09-full -p no:cacheprovider
```

Record exact passed/skipped/warnings. Do not reuse baseline counts as final evidence.

- [ ] **Step 3: Build a clean Windows onedir artifact**

```powershell
.\.venv\Scripts\python.exe tools\build_windows.py
```

Expected artifact: `dist\MR-FARMBOY-Manager\MR-FARMBOY-Manager.exe`.
Preserve any locked historical cache; the build workflow uses its isolated
`build/pyinstaller` work path and `--clean`.

- [ ] **Step 4: Run two automated isolated startup/safety smokes**

```powershell
.\.venv\Scripts\python.exe tools\smoke_windows_build.py dist\MR-FARMBOY-Manager\MR-FARMBOY-Manager.exe
.\.venv\Scripts\python.exe tools\smoke_windows_build.py dist\MR-FARMBOY-Manager\MR-FARMBOY-Manager.exe
```

Both must log `qml.load.completed` and `qml.controller.initialized`, exit cleanly
and report no writes outside the temporary runtime root. These are startup and
safety gates; they do not replace the functional journey below.

- [ ] **Step 5: Run the reproducible visible packaged-UI journey**

1. Create `build/packaged-ui-smoke-20260821/` with `runtime/`, `appdata/`,
   `localappdata/`, `temp/`, `game-install/` and `game_data/save_1/`. Copy only
   the two tracked synthetic files from
   `tests/fixtures/farm_analytics_game_data/save_1/` into that temporary slot.
2. Write only `build/packaged-ui-smoke-20260821/runtime/settings.ini`, with
   `[paths]`, `save_directory` pointing at that temporary `game_data` and
   `game_install_directory` pointing at `game-install`.
3. Launch the packaged executable visibly with `MR_FARMBOY_RUNTIME_ROOT`,
   `APPDATA`, `LOCALAPPDATA`, `TEMP` and `TMP` redirected to those temporary
   directories. Use the `computer-use` workflow for the visible interaction;
   do not point the application at the real save or game installation.
4. Verify and capture screenshots under `screenshots/`: Dashboard shows the
   fixture wallet/harvestable/capacity values; Crops has its fixture row;
   Resources switches through all four origins; People/Animals has worker and
   animal rows; Economy keeps wallet, accumulated earnings and unavailable
   revenue/day visibly separate.
5. Continue the same process: Saves lists `save_1`, supports select and refresh;
   Backups creates a backup only below the temporary runtime root; Settings
   shows both temporary roots as valid; Diagnostics loads and displays events.
6. Close normally. Record the process exit, screenshot paths, temporary backup
   path and observed page states. Confirm no mutable path escaped the temporary
   root, then recompute the original save/game hashes and compare them with the
   schema audit.

- [ ] **Step 6: Perform the final repository audit**

Run `/closing-stale-subagents` and require `pending_count = 0`.

```powershell
git diff --check
git status --short
git fetch origin
git rev-list --left-right --count HEAD...origin/main
git tag --list v0.2.0
```

Expected: no tracked diff, protected local files remain, `0 0`, and no
`v0.2.0` tag. If no code changed during this task, do not create an empty commit.

## Plan Completion Gate

- Typed dictionaries parse safely and all previous parser cases remain green.
- A defensively immutable, provenance-bearing snapshot is built once per stable inspection.
- Analytics exposes only confirmed/derived metrics and keeps unknown values unavailable.
- Alerts cover exact animal capacity, feeder threshold and protected Warehouse stock only.
- Dashboard and four related pages use typed Qt models with no QML aggregation.
- “Trilho de crescimento” and generic `Estado 0..3` presentation are removed.
- Saves `Atualizar` and Dashboard `Configuração ativa` have structural non-overlap tests.
- Layout/visual QA passes at 960×640, 1280×720, 1366×768, 1600×900 and 1920×1080.
- QML/E2E, full pytest, PyInstaller and two isolated smokes pass with fresh evidence.
- Original saves and game installation have zero writes and matching hashes.
- Git is synchronized, protected local files are preserved and zero subagents remain active.
- Version remains prepared at 0.2.0; tag/release remain absent pending user QA.
