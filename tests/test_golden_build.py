"""Golden-file test: rebuild GAIN.ZDL and verify it matches the committed dist/ copy.

Requires cl6x (TI C6000 compiler). The test skips cleanly if the compiler is
not found at the path resolved from TI_CGT_ROOT (or the default CCS install
location). This lets CI environments without the toolchain still import and
discover the test without failing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GAIN_BUILD = ROOT / "src" / "airwindows" / "gain" / "build.py"
GOLDEN_ZDL = ROOT / "dist" / "GAIN.ZDL"

_TI_ROOT = Path(os.environ.get(
    "TI_CGT_ROOT",
    "/Applications/ti/ccs2050/ccs/tools/compiler/ti-cgt-c6000_8.5.0.LTS"))
_CL6X = _TI_ROOT / "bin" / "cl6x"


def _has_compiler() -> bool:
    return _CL6X.exists()


@pytest.mark.skipif(not _has_compiler(), reason=f"cl6x not found at {_CL6X}; set TI_CGT_ROOT")
def test_gain_golden_rebuild(tmp_path: Path) -> None:
    """Rebuild GAIN.ZDL and byte-compare it to the committed golden copy."""
    assert GOLDEN_ZDL.exists(), f"golden file missing: {GOLDEN_ZDL}"

    golden_bytes = GOLDEN_ZDL.read_bytes()

    # Move the existing output aside so the build always writes a fresh file.
    backup = tmp_path / "GAIN.ZDL.bak"
    shutil.copy2(GOLDEN_ZDL, backup)

    try:
        result = subprocess.run(
            [sys.executable, "-B", str(GAIN_BUILD)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if result.returncode != 0:
            pytest.fail(f"build.py failed:\n{result.stdout}\n{result.stderr}")

        rebuilt_bytes = GOLDEN_ZDL.read_bytes()
    except Exception:
        # Restore golden on any unexpected error.
        shutil.copy2(backup, GOLDEN_ZDL)
        raise

    if rebuilt_bytes != golden_bytes:
        # Restore so the working tree stays clean after a failure.
        shutil.copy2(backup, GOLDEN_ZDL)
        pytest.fail(
            f"Rebuilt GAIN.ZDL differs from committed golden copy.\n"
            f"  golden:   {len(golden_bytes)} bytes\n"
            f"  rebuilt:  {len(rebuilt_bytes)} bytes\n"
            "Run the build manually and commit the updated dist/GAIN.ZDL if the "
            "change is intentional."
        )
