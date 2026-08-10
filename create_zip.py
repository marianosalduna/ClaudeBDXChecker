#!/usr/bin/env python3
"""
Packaging Script — creates a deployable ZIP of the BDX Integrity Checker.

Usage:
    python create_zip.py

Output:
    bdx_integrity_checker.zip

The ZIP can be imported directly into Replit and run without modification.
"""

import os
import zipfile
import sys
from pathlib import Path
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────
OUTPUT_NAME = "bdx_integrity_checker.zip"
PROJECT_ROOT = Path(__file__).parent.resolve()

# Files and directories to include
INCLUDE_PATTERNS = [
    "app.py",
    "requirements.txt",
    ".replit",
    "replit.nix",
    "config_sample.yaml",
    "README.md",
    "LICENSE",
    "create_zip.py",
    ".streamlit/config.toml",
    "modules/__init__.py",
    "modules/file_handler.py",
    "modules/column_detector.py",
    "modules/blank_column_detector.py",
    "modules/excel_table_validator.py",
    "modules/signature_engine.py",
    "modules/policy_validator.py",
    "modules/sort_simulator.py",
    "modules/reconciliation.py",
    "modules/tieout_engine.py",
    "modules/risk_scorer.py",
    "modules/recommendations.py",
    "modules/reporter.py",
    "modules/sample_data.py",
    "tests/__init__.py",
    "tests/test_blank_column_detector.py",
    "tests/test_policy_validator.py",
    "tests/test_signature_engine.py",
    "tests/test_risk_scorer.py",
    "tests/test_excel_table_validator.py",
    "tests/test_sort_simulator.py",
]

# Directories to recurse into (include all .py files)
INCLUDE_DIRS = []

# Patterns to explicitly exclude
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".egg-info"}
EXCLUDE_DIRS = {"__pycache__", ".git", ".mypy_cache", "node_modules", "venv", ".venv"}


def should_exclude(path: Path) -> bool:
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def collect_files() -> list[tuple[Path, str]]:
    """Return list of (absolute_path, archive_name) pairs."""
    files: list[tuple[Path, str]] = []
    seen = set()

    for pattern in INCLUDE_PATTERNS:
        full = PROJECT_ROOT / pattern
        if full.exists():
            arc = str(Path(pattern))
            if arc not in seen:
                files.append((full, arc))
                seen.add(arc)
        else:
            print(f"  [WARN] Not found, skipping: {pattern}")

    # Recurse extra directories
    for d in INCLUDE_DIRS:
        dir_path = PROJECT_ROOT / d
        if dir_path.is_dir():
            for fp in dir_path.rglob("*"):
                if fp.is_file() and not should_exclude(fp):
                    arc = str(fp.relative_to(PROJECT_ROOT))
                    if arc not in seen:
                        files.append((fp, arc))
                        seen.add(arc)

    return files


def create_zip():
    output_path = PROJECT_ROOT / OUTPUT_NAME
    files = collect_files()

    print(f"\nBDX Integrity Checker — Packaging Script")
    print(f"{'='*50}")
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Output file  : {output_path}")
    print(f"Files to pack: {len(files)}")
    print()

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for abs_path, arc_name in files:
            zf.write(abs_path, arc_name)
            print(f"  + {arc_name}")

    size_kb = output_path.stat().st_size / 1024
    print(f"\n✅ Package created: {output_path}")
    print(f"   Size: {size_kb:.1f} KB")
    print(f"   Files: {len(files)}")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("To deploy on Replit:")
    print("  1. Create a new Replit project (Python)")
    print("  2. Upload bdx_integrity_checker.zip")
    print("  3. Open the Shell and run: unzip bdx_integrity_checker.zip")
    print("  4. Click Run")
    print()
    return output_path


if __name__ == "__main__":
    create_zip()
