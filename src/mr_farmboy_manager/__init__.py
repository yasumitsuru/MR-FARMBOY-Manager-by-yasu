"""MR FARMBOY Manager by yasu - Módulo principal da aplicação."""

from mr_farmboy_manager.save_inspector import (
    DetectedFormat,
    SaveInspectionResult,
    calculate_file_hash,
    inspect_save,
    verify_file_integrity,
)
from mr_farmboy_manager.save_loader import (
    SaveLoadResult,
    load_save,
)
from mr_farmboy_manager.save_discovery import (
    SaveDiscoveryResult,
    SavedFormat as SaveDiscoverySavedFormat,
    discover_save_structure,
    format_sanitized_report,
)
from mr_farmboy_manager.godot_variant import (
    GodotVariant,
    GodotVariantKind,
    GodotVariantLimitError,
    GodotVariantParseError,
    parse_godot_variant,
)
from mr_farmboy_manager.godot_tres import (
    GodotTresDocument,
    GodotTresParseError,
    GodotTresProfile,
    GodotTresProperty,
    GodotTresSection,
    GodotTresSectionKind,
    is_godot_tres_text,
    parse_godot_tres_document,
    parse_godot_tres_structure,
)
from mr_farmboy_manager.save_snapshot import (
    SnapshotResult,
    create_save_snapshot,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # save_loader
    "SaveLoadResult",
    "load_save",
    # save_snapshot
    "SnapshotResult",
    "create_save_snapshot",
    # godot_variant
    "GodotVariant",
    "GodotVariantKind",
    "GodotVariantLimitError",
    "GodotVariantParseError",
    "parse_godot_variant",
    # godot_tres
    "GodotTresDocument",
    "GodotTresParseError",
    "GodotTresProfile",
    "GodotTresProperty",
    "GodotTresSection",
    "GodotTresSectionKind",
    "is_godot_tres_text",
    "parse_godot_tres_document",
    "parse_godot_tres_structure",
    # save_inspector
    "DetectedFormat",
    "SaveInspectionResult",
    "calculate_file_hash",
    "inspect_save",
    "verify_file_integrity",
    # save_discovery
    "SaveDiscoveryResult",
    "SaveDiscoverySavedFormat",
    "discover_save_structure",
    "format_sanitized_report",
]