#!/usr/bin/env python3
"""Build PLL.ZDL, the dual-voice integer-N digital PFD/PI/VCO PLL."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT / "src/airwindows/common"))
from linker import LinkerConfig, link, params_from_manifest
from manifest_params import write_param_header
from screen_image import Canvas, encode_zoom_rle

TI_ROOT = Path(os.environ.get(
    "TI_CGT_ROOT",
    "/Applications/ti/ccs2050/ccs/tools/compiler/ti-cgt-c6000_8.5.0.LTS"))


def make_cover() -> bytes:
    """Render a simple PLL-themed 128x64 effect screen."""
    c = Canvas()
    c.rect(0, 0, 127, 63)
    c.draw_text("PLL", 7, 5, scale=2, spacing=1)
    c.hline(6, 121, 22)
    for x, high in ((12, 8), (24, 13), (36, 8), (48, 13),
                    (60, 8), (72, 13), (84, 8), (96, 13)):
        c.vline(x, 31 - high, 31)
        c.hline(x, x + 5, 31 - high)
        c.vline(x + 5, 31 - high, 31)
    c.draw_text("Speed", 13, 36, scale=1, spacing=1)
    c.draw_text("Damp", 57, 36, scale=1, spacing=1)
    c.draw_text("Level", 96, 36, scale=1, spacing=1)
    c.rect(7, 47, 39, 61)
    c.rect(48, 47, 80, 61)
    c.rect(89, 47, 121, 61)
    return encode_zoom_rle(c)


def main() -> None:
    manifest = json.loads((HERE / "manifest.json").read_text())
    write_param_header(manifest, HERE / "pll_params.h", "PLL")
    obj = HERE / "pll.obj"
    output = ROOT / "dist/PLL.ZDL"
    output.parent.mkdir(exist_ok=True)
    subprocess.run([
        str(TI_ROOT / "bin/cl6x"), "--c99", "--opt_level=2", "-mv6740",
        "--abi=eabi", "--mem_model:data=far", f"--include_path={TI_ROOT}/include",
        f"--define=PLL_AUDIO_FUNC={manifest['audio_func_name']}",
        "-c", str(HERE / "pll.c"), f"--output_file={obj}",
    ], cwd=HERE, check=True)
    link(LinkerConfig(
        materialize_init=True,
        effect_name=manifest["effect_name"], audio_func_name=manifest["audio_func_name"],
        screen_image=make_cover(),
        gid=manifest["gid"], fxid=manifest["fxid"],
        fxid_version=manifest["fxid_version"].encode("ascii"),
        flags_byte=manifest["flags_byte"], audio_nop=manifest.get("audio_nop", False),
        params=params_from_manifest(manifest["params"]),
        obj_path=obj, output_path=output,
        knob_positions=[(2, 14, 46), (3, 55, 46), (4, 96, 46)],
        use_object_edit_handlers=False, synthesize_linesel_edit_handlers=True,
        synth_edit_start_index=2, knob3_blob_path="/tmp/__nonexistent__",
    ))
    print(f"[pll] done -> {output}")


if __name__ == "__main__":
    main()
