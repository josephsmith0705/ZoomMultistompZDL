"""Parameter-load regressions; runs with stdlib unittest (no TI dependency)."""
from __future__ import annotations

import ast
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import linker
sys.path.insert(0, str(ROOT))
from build_all import RELEASE_PLUGINS


def branch_target(body: bytes, offset: int, pc: int) -> int:
    word = struct.unpack_from("<I", body, offset)[0]
    if word & ~(0x1FFFFF << 7) != 0x12:
        raise AssertionError("expected direct B.S2")
    delta = (word >> 7) & 0x1FFFFF
    if delta & (1 << 20):
        delta -= 1 << 21
    return (pc & ~31) + delta * 4


def sections(data: bytes) -> dict[str, tuple[int, bytes]]:
    """Read linked ELF sections without depending on the stock corpus."""
    elf = data[data.index(b"\x7fELF"):]
    shoff = struct.unpack_from("<I", elf, 0x20)[0]
    stride, count, string_index = struct.unpack_from("<HHH", elf, 0x2E)
    headers = [struct.unpack_from("<10I", elf, shoff + i * stride)
               for i in range(count)]
    strings = headers[string_index]
    names = elf[strings[4]:strings[4] + strings[5]]
    return {names[h[0]:].split(b"\0", 1)[0].decode():
            (h[3], elf[h[4]:h[4] + h[5]]) for h in headers}


class InitMaterialization(unittest.TestCase):
    def test_packet_sizes(self):
        for chunk in (linker._INIT_MAT_PROLOGUE, linker._INIT_MAT_CALL_BLOCK,
                      linker._INIT_MAT_EPILOGUE):
            self.assertEqual(len(chunk), 64)

    def test_calls_follow_text_rebase(self):
        init_va = 0x7A0
        targets = [0x380, 0x3CC, 0x1800]
        body = linker._init_materialize_body(targets, init_va)
        for i, target in enumerate(targets):
            off = len(linker._INIT_MAT_PROLOGUE) + i * linker._INIT_MAT_STRIDE
            off += linker._INIT_MAT_BRANCH_OFF
            for load_base in (0, 0x10000000, 0x11820000):
                self.assertEqual(branch_target(body, off, load_base + init_va + off),
                                 load_base + target)

    def test_empty_init_keeps_frame(self):
        self.assertEqual(linker._init_materialize_body([], 0x7A0),
                         linker._INIT_MAT_PROLOGUE + linker._INIT_MAT_EPILOGUE)

    def test_rejects_invalid_branch_layout(self):
        for targets, base in (([0x380], 1), ([0x381], 0x7A0), ([0x800000], 0x7A0)):
            with self.assertRaises(ValueError):
                linker._init_materialize_body(targets, base)

    def test_every_release_build_enables_materialization(self):
        for name, build_script in RELEASE_PLUGINS:
            with self.subTest(effect=name):
                tree = ast.parse(build_script.read_text())
                calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Name)
                         and node.func.id == "LinkerConfig"]
                self.assertEqual(len(calls), 1)
                opts = {kw.arg: kw.value for kw in calls[0].keywords}
                self.assertIs(ast.literal_eval(opts["materialize_init"]), True)

    def test_release_binaries_call_their_descriptor_handlers(self):
        for name, build_script in RELEASE_PLUGINS:
            with self.subTest(effect=name):
                manifest = json.loads((build_script.parent / "manifest.json").read_text())
                output_name = manifest.get("output_basename", manifest["effect_name"])
                path = ROOT / "dist" / f"{output_name}.ZDL"
                self.assertTrue(path.exists(), f"build {name} first: {path}")
                sec = sections(path.read_bytes())
                text_va, text = sec[".text"]
                _, const = sec[".const"]
                desc = const.index(b"OnOff\0")
                init_va = struct.unpack_from("<I", const, desc + 0x30 + 0x1C)[0]
                init_off = init_va - text_va
                count = len(manifest["params"])
                size = 128 + 64 * count
                body = text[init_off:init_off + size]
                self.assertEqual(body[:64], linker._INIT_MAT_PROLOGUE)
                self.assertEqual(body[-64:], linker._INIT_MAT_EPILOGUE)
                for i in range(count):
                    handler = struct.unpack_from("<I", const, desc + (i + 2) * 0x30 + 0x1C)[0]
                    off = 64 + i * 64 + linker._INIT_MAT_BRANCH_OFF
                    self.assertEqual(branch_target(body, off, init_va + off), handler)
                # The original bug also risks overwriting the following Dll.
                self.assertLessEqual(init_off + size, len(text))


if __name__ == "__main__":
    unittest.main()