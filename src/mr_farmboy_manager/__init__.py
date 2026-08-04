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
    # save_inspector
    "DetectedFormat",
    "SaveInspectionResult",
    "calculate_file_hash",
    "inspect_save",
    "verify_file_integrity",
]