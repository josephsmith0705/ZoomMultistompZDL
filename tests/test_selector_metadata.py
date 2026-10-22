"""Selector generation, portable formatter checks, and linked PLL metadata."""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT / "src/airwindows/common"))
import linker
from manifest_params import write_param_header
from selector_metadata import SELECTORS
from tests.test_init_materialize import sections


class SelectorMetadata(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "src/custom/pll/manifest.json").read_text())

    def test_generated_header_includes_only_selector_callbacks(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ):
            os.environ.pop("ZDL_SELECTOR_LABELS", None)
            header = Path(folder) / "params.h"
            write_param_header(self.manifest, header, "PLL")
            code = header.read_text()
            for i, param in enumerate(self.manifest["params"]):
                self.assertEqual(f"int ZDL_GetLabel_{i}(" in code,
                                 param["name"] in SELECTORS["PLL"])
            # Preserve the selector's raw 0..7 parameter ABI and legitimate zero.
            self.assertIn("#define PLL_MULT_UI_MAX 7", code)
            self.assertIn("#define PLL_MULT_DEFAULT_NORM 0.0f", code)

    def test_callbacks_can_be_disabled_and_stale_content_is_removed(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ):
            header = Path(folder) / "params.h"
            os.environ["ZDL_SELECTOR_LABELS"] = "1"
            write_param_header(self.manifest, header, "PLL")
            self.assertIn("ZDL_GetLabel_", header.read_text())
            os.environ["ZDL_SELECTOR_LABELS"] = "0"
            write_param_header(self.manifest, header, "PLL")
            self.assertNotIn("ZDL_GetLabel_", header.read_text())

    def test_selector_range_mismatch_fails_generation(self):
        self.manifest["params"][3]["max"] = 8
        with tempfile.TemporaryDirectory() as folder, patch.dict(
                os.environ, {"ZDL_SELECTOR_LABELS": "1"}):
            with self.assertRaisesRegex(ValueError, "selector range mismatch"):
                write_param_header(self.manifest, Path(folder) / "params.h", "PLL")

    def test_unmapped_effect_has_no_callbacks(self):
        self.manifest["effect_name"] = "NoSelectors"
        with tempfile.TemporaryDirectory() as folder, patch.dict(
                os.environ, {"ZDL_SELECTOR_LABELS": "1"}):
            header = Path(folder) / "params.h"
            write_param_header(self.manifest, header, "TEST")
            self.assertNotIn("ZDL_GetLabel_", header.read_text())

    @unittest.skipUnless(shutil.which("cc"), "host C compiler required")
    def test_all_labels_lengths_and_output_bounds(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(
                os.environ, {"ZDL_SELECTOR_LABELS": "1"}):
            folder = Path(folder)
            write_param_header(self.manifest, folder / "params.h", "PLL")
            code = ['#include <assert.h>', '#include <string.h>',
                    '#include "params.h"', 'int main(void) {']
            for i, param in enumerate(self.manifest["params"]):
                choices = SELECTORS["PLL"].get(param["name"], [])
                for choice in choices:
                    label = json.dumps(choice["label"])
                    for raw in (choice["from"], choice["to"]):
                        code.extend([
                            '{ char out[10]; memset(out, 0x55, sizeof(out));',
                            f'int n = ZDL_GetLabel_{i}({raw}u, out + 1);',
                            f'assert(n == {len(choice["label"])});',
                            f'assert(strcmp(out + 1, {label}) == 0);',
                            'assert(out[0] == 0x55 && out[9] == 0x55); }',
                        ])
            code.append('return 0; }')
            source, binary = folder / "labels.c", folder / "labels"
            source.write_text("\n".join(code))
            subprocess.run([shutil.which("cc"), "-std=c99", "-O2", str(source),
                            "-o", str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)

    def test_pll_binary_has_formatters_and_relocatable_label_strings(self):
        binary = ROOT / "dist/PLL.ZDL"
        self.assertTrue(binary.exists(), "build PLL first")
        sec = sections(binary.read_bytes())
        text_va, text = sec[".text"]
        const_va, const = sec[".const"]
        desc = const.index(b"OnOff\0")
        dynsym = sec[".dynsym"][1]
        relocs = {}
        for offset, info, addend in struct.iter_unpack("<IIi", sec[".rela.dyn"][1]):
            target = struct.unpack_from("<I", dynsym, (info >> 8) * 16 + 4)[0]
            relocs[offset] = (info & 0xFF, target + addend)
        pointers = []
        for i, param in enumerate(self.manifest["params"]):
            offset = desc + (i + 2) * 0x30 + 0x24
            pointer = struct.unpack_from("<I", const, offset)[0]
            choices = SELECTORS["PLL"].get(param["name"])
            if not choices:
                self.assertEqual(pointer, 0)
                self.assertNotIn(const_va + offset, relocs)
                continue
            self.assertGreaterEqual(pointer, text_va)
            self.assertLess(pointer, text_va + len(text))
            self.assertEqual(relocs[const_va + offset], (linker.RT_ABS32, pointer))
            pointers.append(pointer)
            # Every literal used by the C callbacks must survive .const rebasing,
            # not just have its build-time address patched into .text.
            for choice in choices:
                target = const_va + const.index(choice["label"].encode() + b"\0")
                for kind in (linker.RT_ABS_L16, linker.RT_ABS_H16):
                    self.assertTrue(any(text_va <= site < text_va + len(text)
                                        and reloc == (kind, target)
                                        for site, reloc in relocs.items()),
                                    f"missing runtime relocation for {choice['label']}")
        self.assertEqual(len(set(pointers)), 2)


if __name__ == "__main__":
    unittest.main()