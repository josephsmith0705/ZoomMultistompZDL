"""Host-compiled PLL core smoke test; no numpy, scipy, or TI tools required.

This tests DSP with manifest-derived materialized parameters, not firmware
dispatch. The linked-ZDL initialization contract is tested separately.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("cc"), "host C compiler required")
class PLLAudio(unittest.TestCase):
    def test_default_controls_are_audible_and_zero_level_mutes(self):
        manifest = json.loads((ROOT / "src/custom/pll/manifest.json").read_text())
        controls = {p["name"]: p["default"] / p["max"]
                    for p in manifest["params"]}
        code = r'''
#include <math.h>
#include <stdio.h>
#include "pll_dsp.h"
int main(void) {
    PLLState s;
    tp_init(&s, tp_center_hz(0.0f));
    float speed = SPEED, damping = DAMP;
    float omega = TP_TWO_PI * tp_bandwidth_hz(speed);
    float kp = 2.0f * tp_damping_ratio(damping) * omega;
    float ki = omega * omega;
    float energy = 0.0f, peak = 0.0f;
    for (int i = 0; i < 44100; ++i) {
        float in = 0.2f * sinf(TP_TWO_PI * 220.0f * (float)i * TP_INV_SR);
        float l, r;
        tp_process(&s, in, in, 0.0001f, 55.0f, kp, ki, 1.0f,
                   1u, 0.5f, LEVEL, HILVL, LOLVL, &l, &r);
        if (!isfinite(l) || l != r || fabsf(l) > 1.0f) return 1;
        energy += l * l;
        if (fabsf(l) > peak) peak = fabsf(l);
    }
    if (energy < 1.0f || peak < 0.01f) return 2;
    float l, r;
    tp_process(&s, 0.1f, 0.1f, 0.0001f, 55.0f, kp, ki, 1.0f,
               1u, 0.5f, 0.0f, HILVL, LOLVL, &l, &r);
    if (l != 0.0f || r != 0.0f) return 3;
    printf("PLL default audio: energy=%g peak=%g; zero Level mutes\n", energy, peak);
    return 0;
}
'''
        for key in ("Speed", "Damp", "Level", "HiLvl", "LoLvl"):
            code = code.replace(key.upper(), f"{controls[key]:.9f}f")
        with tempfile.TemporaryDirectory(prefix="pll-audio-test-") as folder:
            source = Path(folder) / "pll_audio.c"
            binary = Path(folder) / "pll_audio"
            source.write_text(code)
            subprocess.run([shutil.which("cc"), "-std=c99", "-O2",
                            "-I", str(ROOT / "src/custom/pll"), str(source),
                            "-lm", "-o", str(binary)], check=True, capture_output=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()