"""PLL preview runs the same dual-voice PFD/PI/VCO C core as the pedal."""
from __future__ import annotations
import ctypes
import functools
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
from scipy.signal import resample_poly

DEFAULTS = {"speed": 100, "damping": 32, "level": 80, "mult": 0, "div": 0,
            "hilvl": 100, "lolvl": 100}
MAXIMA = {"speed": 1000, "damping": 100, "level": 100, "mult": 7, "div": 7,
          "hilvl": 100, "lolvl": 100}


@functools.lru_cache(maxsize=1)
def host_library():
    compiler = shutil.which("cc")
    if not compiler:
        raise RuntimeError("PLL preview requires a host C compiler (cc).")
    folder = Path(__file__).resolve().parents[3] / "src/custom/pll"
    temporary = tempfile.TemporaryDirectory(prefix="pll-preview-")
    tmp = Path(temporary.name)
    source = tmp / "host.c"
    source.write_text('''
#include "pll_dsp.h"
int tp_render(float *input,float *output,float *freq,float *low,int n,float center,
              float kp,float ki,float vcoGain,unsigned int multiplier,
              float dividerHalfRecip,float level,float highLevel,float lowLevel,float *last){
 PLLState s;tp_init(&s,center);
 for(int i=0;i<n;i++){
  tp_process(&s,input[i],input[i],0.0001f,center,kp,ki,vcoGain,multiplier,
             dividerHalfRecip,level,highLevel,lowLevel,&output[2*i],&output[2*i+1]);
  freq[i]=s.frequency;
  low[i]=s.dividerPhase<.5f?1.f:-1.f;
 }
 last[0]=s.frequency;last[1]=s.integrator;last[2]=s.phase;
 return 0;
}
void tp_derived(float speed,float damping,float multKnob,float divKnob,float *v){
 float hz=tp_bandwidth_hz(speed),omega=TP_TWO_PI*hz;
 float zeta=tp_damping_ratio(damping);
 unsigned int mult=tp_ratio_from_knob(multKnob);
 unsigned int div=tp_ratio_from_knob(divKnob);
 v[0]=tp_center_hz(0.f);
 v[1]=2.f*zeta*omega*(1.f)*(float)mult;
 v[2]=omega*omega*(1.f)*(float)mult;
 v[3]=1.f;
 v[4]=(float)mult;
 v[5]=.5f*tp_recip((float)div);
}
float tp_test_internal_speed(float knob){return tp_internal_speed(knob);}
float tp_test_bandwidth(float knob){return tp_bandwidth_hz(knob);}
float tp_test_damping(float knob){return tp_damping_ratio(knob);}
''')
    library = tmp / "host.so"
    subprocess.run([compiler, "-std=c99", "-O2", "-ffp-contract=off", "-shared", "-fPIC",
                    "-I", str(folder), str(source), "-o", str(library)], check=True, capture_output=True)
    lib = ctypes.CDLL(str(library))
    ptr = np.ctypeslib.ndpointer(dtype=np.float32, flags="C_CONTIGUOUS")
    lib.tp_render.argtypes = [ptr, ptr, ptr, ptr, ctypes.c_int, ctypes.c_float,
                              ctypes.c_float, ctypes.c_float, ctypes.c_float,
                              ctypes.c_uint, ctypes.c_float, ctypes.c_float,
                              ctypes.c_float, ctypes.c_float, ptr]
    lib.tp_render.restype = ctypes.c_int
    lib.tp_derived.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float,
                               ctypes.c_float, ptr]
    for name in ("tp_test_internal_speed", "tp_test_bandwidth", "tp_test_damping"):
        fn = getattr(lib, name)
        fn.argtypes = [ctypes.c_float]
        fn.restype = ctypes.c_float
    lib._temporary = temporary
    return lib


def core(mono, params=None, include_low=False):
    """Run at 44.1k; optionally include the edge-divider low-voice trace."""
    p = DEFAULTS.copy()
    p.update(params or {})
    norm = {name: np.float32(value / MAXIMA[name]) for name, value in p.items()}
    norm["mult"] = np.float32(p["mult"] * 0.01)
    norm["div"] = np.float32(p["div"] * 0.01)
    derived = np.empty(6, np.float32)
    host_library().tp_derived(norm["speed"], norm["damping"],
                              norm["mult"], norm["div"], derived)
    center, kp, ki, vcoGain, multiplier, dividerHalfRecip = derived
    x = np.ascontiguousarray(mono, dtype=np.float32)
    output = np.empty((len(x), 2), np.float32)
    trace = np.empty(len(x), np.float32)
    low = np.empty(len(x), np.float32)
    last = np.empty(3, np.float32)
    host_library().tp_render(x, output.reshape(-1), trace, low, len(x), center,
                             kp, ki, vcoGain, int(multiplier), dividerHalfRecip,
                             norm["level"], norm["hilvl"], norm["lolvl"], last)
    return (output, trace, last, low) if include_low else (output, trace, last)


def render(audio, sample_rate, params, tail, root):
    values = DEFAULTS.copy()
    for name, default in DEFAULTS.items():
        v = float(params.get(name, default))
        values[name] = v if np.isfinite(v) and 0 <= v <= MAXIMA[name] else default
    x = np.asarray(audio)
    if x.ndim == 1:
        x = x[:, None]
    x = np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x[:, :2]
    x = np.pad(x, ((0, max(0, int(tail * sample_rate))), (0, 0)))
    if not len(x):
        return x.copy()
    original_length = len(x)
    if sample_rate != 44100:
        common = math.gcd(int(sample_rate), 44100)
        x = resample_poly(x, 44100 // common, int(sample_rate) // common, axis=0)
    y = core(x[:, 0], values)[0]
    if sample_rate != 44100:
        y = resample_poly(y, int(sample_rate) // common, 44100 // common, axis=0)
    return y[:original_length]
