# SyncCalc — §4 algorithm validator (v1)

The first probe that tests TEMPO-SYNC.md §4's central claim: **does the
firmware's `state[24]` consult tempo state internally**, or is it pure
float math?

If §4 is right, replicating TapeEcho3's `state[31](B4=0x0f3c)` +
`state[24](B4=100)` + `/100` chain gives a tempo-tracking delay value.
If `state[24]` is just math, the BPM has to fold in via the
`state[31](B4=0x0f3c)` table lookup at `0xc009fe90` — and a different
probe (v2) is needed.

## How it works

The audio function calls `state[24]` directly using its template-writer
firmware address, `c00d4b40`. No new edit handler is authored; the
LineSel handler is reused unchanged. This avoids the
"object-defined edit handlers crash on interaction" risk noted in the
memory.

```c
typedef unsigned int (*fw_state_fn)(unsigned int a4, unsigned int b4);
fw_state_fn fw_state24 = (fw_state_fn)0xc00d4b40u;

float a4_float = (float)(idx + 1);            /* 1.0 .. 16.0 */
union { float f; unsigned int u; } a4u = { a4_float };
unsigned int y = fw_state24(a4u.u, 0x42C80000u /* float(100.0) */);

unsigned int byte_sum = ... /* sum of all four bytes of y */ ...;
float gain = (float)byte_sum * (1.0f / 510.0f);
```

The `Sync` knob (0..15, `flags=0x28`) carries the TAP UI button so tap
tempo is reachable while the audio function is running.

## Test plan

Two distinct experiments share the same probe.

### Q1: Does `state[24]` return varying values for varying A4?

At a fixed BPM (default 120), sweep `Sync` 0 → 15 slowly.

| observation | implication |
|---|---|
| Audible gain changes smoothly per position | `state[24]` is a real function of A4, our call interface works |
| Audible gain stays constant across all 16 positions | call interface is broken, OR state[24] saturates/ignores A4 |
| Audio cuts out at one or more positions | those A4 values trigger an early-exit or saturate to zero |

### Q2: Does `state[24]` consult tempo state?

Pick a `Sync` position that gave mid-range gain (not silent, not
saturated). Then:

1. Tap-tempo to ~75 BPM. Listen.
2. Tap-tempo to ~250 BPM. Listen.
3. Compare the two gains.

| observation | implication |
|---|---|
| Gain CHANGES with tap tempo | `state[24]` is tempo-aware. §4 is right — replicate TAPEECH3's call pattern. |
| Gain STAYS THE SAME with tap tempo | `state[24]` is pure float math. §4 is wrong about BPM folding here. Tempo must fold in via the `0xc009fe90` table or another path; build v2 to probe. |

## Risks

* **Calling firmware from audio context.** `state[24]` is leaf math —
  it does `ABSSP / CMPEQSP / RCPSP / MPYSP` and returns. No IO, no
  peripheral access. Should be safe, but this is the first time we
  call a firmware function pointer directly from audio code. If the
  pedal freezes on load or on unbypass, the call interface is broken.
* **Argument bit shapes.** `state[24]`'s prologue treats `A4` and `B4`
  as floats (`ABSSP A4,A7; ABSSP B4,B7`). We pass `A4 = float(idx+1)`
  and `B4 = float(100.0)` — both non-zero floats — to avoid the
  `CMPEQSP 0` early-exit at the top of `c00d4b40`. TAPEECH3 reportedly
  uses `MVK B4,100` (int 100, denormal float ≈ 0). Either the static
  trace is slightly off, or `state[24]`'s `CMPEQSP` doesn't catch
  denormals as zero. Our float(100.0) avoids the question entirely.
* **Tap-tempo arming.** The TAP UI is wired on the `Sync` slot. If
  the TAP button doesn't appear on left-knob click, the descriptor
  flags didn't take.

## How it was built

```
python3 src/hardware_probes/synccalc/build.py
```

Uses the **unpatched** `linesel_handlers.bin`. The audio function does
all the work.
