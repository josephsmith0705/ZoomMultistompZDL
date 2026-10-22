# PLL — digital analogue-style PLL

PLL is now a deliberately conventional digital model of an **analog
phase-locked loop**, based on the standard loop structure described in Analog Devices'
[PLL Fundamentals](https://www.analog.com/media/en/analog-dialogue/volume-52/number-3/phase-locked-loop-pll-fundamentals.pdf).

## Signal/control loop

1. **Reference input and phase-frequency detector (PFD):** the left input uses
  a Schmitt detector (positive crossing sets, negative crossing re-arms). A
  second edge stream comes from the multiplied VCO feedback. UP and DOWN
  latches stay asserted until the other edge arrives. Their pulse-width
   difference gives signed phase error; a latch that remains set also indicates
   frequency error during acquisition / cycle slips. Unlike the previous
   simultaneous-edge `−1/0/+1` detector, the PFD preserves which edge led and
   for how long.
2. **PI loop filter:** the signed PFD signal enters proportional and integral
  paths. For loop natural frequency $\omega_n$ and damping $\zeta$,
  $$K_p=2\zeta\omega_n G_p,\qquad K_i=\omega_n^2 G_i.$$
  The proportional path responds to present phase error; the integrator holds
  the frequency correction needed to stay locked. The P/I/V gains are fixed at
  50 (unity). Integration has anti-windup at the VCO rails.
3. **Multiplied master VCO:** Mult N lets one VCO edge reach the PFD for each N
  oscillator cycles. At lock the master output is about N times the guitar
  input: Mult 2 is an octave up, Mult 3 a twelfth up, Mult 8 three octaves up.
4. **Input-edge divider voice:** Div does not divide the smoothed PLL VCO. It
  counts both-polarity input Schmitt crossings, advancing a second oscillator
  phase by half a cycle per Div crossings. Its rate is input-frequency / Div,
  so it follows guitar pitch immediately and does not glide with PLL Speed.
  This is the subharmonic/divider source: a basic countered edge train, not a
  second PLL or another pitch loop.
5. **Voice output:** the master phase gives the high square voice, the
  input-edge divider phase gives the low square voice. HiLvl and LoLvl set the
  two voice levels independently; Level is the shared output trim. At Mult=1 /
  Div=1 they are the same pitch, and their rising edges align when locked.
6. **VCO:** the fixed Center value 0 (55 Hz) plus PI correction sets the master
  frequency, clamped to 0–5,400 Hz. Its phase accumulator runs at 44.1 kHz and generates the high
  50%-duty square wave.

In a phase-locked state the detector alternates narrow UP/DOWN pulses whose
average is the residual phase error; the integral term supplies the steady
frequency correction. With no reference, the PFD holds one direction and the
VCO moves toward its low or high limit. That is natural loop behavior, not a
silence gate. The existing DC blocker, Level and Zoom ABI remain output-side
conditioning, not part of the loop filter; output is fixed at 100% wet.

## Controls

| Control | Default | Behavior |
| --- | ---: | --- |
| Speed | 100 | UI 0–1000 maps linearly to the natural-frequency formula; default is 8 Hz |
| Damping | 32 | Full 0–100 range; default preserves approximately $\zeta=0.707$ |
| Level | 80 | Shared output trim, 0–100% |
| Mult | 1× | Eight discrete choices, 1×–8×; multiplies the PLL master VCO |
| Div | 1/1 | Eight discrete choices, 1/1–1/8; divides input edges for the low voice |
| HiLvl | 100 | Multiplied high-voice level, 0–100% |
| LoLvl | 100 | Input-edge-divided low-voice level, 0–100% |

Input threshold is fixed to the former Input=0 setting (0.0001); output is
full-wet. Center is fixed at knob value 0 (55 Hz); P Gain, I Gain and VCO Gain
are fixed at 50 (unity). HiLvl and LoLvl independently scale their voices before
the shared Level trim; at both defaults of 100%, their average preserves the
previous equal voice blend.

Speed maps the UI's normalized 0–1 position to internal values 0–1000; the loop
natural frequency is `0.5 + 7.5 × (internalSpeed/100)^2`. Thus UI Speed 0 gives
0.5 Hz, Speed 100 gives 8 Hz, and Speed 1000 gives 750.5 Hz. The VCO free-runs
from its fixed 55 Hz starting point; when locked, the PI integrator shifts it to
the target. Input tracking remains amplitude-sensitive.

At defaults, Damping 32 and the fixed P/I/V gains preserve approximately 0.707
damping with unity gain trims. The default Speed 100 gives an 8 Hz natural
frequency. Keep damping fixed while sweeping Speed, then change one loop control
at a time.

Control order is **Speed, Damping, Level / Mult, Div, HiLvl, LoLvl** (seven
controls). Mult and Div each have exactly eight displayed choices; each knob
position selects one ratio with no intermediate values. Re-dial/save controls
after upgrading because removed controls changed the parameter slots. Changing
Mult resets its feedback counter/latch; changing Div affects only the low voice.
Both PI coefficients scale by Mult N to compensate approximately for the N
divider's reduced feedback gain. The low voice follows input crossings and is
independent of Speed.

The two VCO voices are averaged and output full-wet. Guitar itself is not mixed
or ring-modulated; that would require a separate output feature.

## Simple code tour

The code is split between [`pll.c`](pll.c), which talks to the Zoom
firmware and reads the knobs, and [`pll_dsp.h`](pll_dsp.h), which
contains the PLL math. The C core is shared with the desktop preview.

### The knobs

| Pedal label | Manifest/control | In plain language |
| --- | --- | --- |
| Speed | Speed | Maps UI 0–1000 to the natural-frequency formula; higher values increase loop response and may increase jitter/cycle slips. |
| Damp | Damping | Full range 0–100. Lower values ring/overshoot; higher values settle more gently. |
| Level | Level | Shared output trim for both voices. |
| Mult | Mult | Eight-step PLL master frequency multiplier 1×–8×. |
| Div | Div | Eight-step input-edge divider 1/1–1/8; it does not glide with Speed. |
| HiLvl | HiLvl | Output level of the multiplied high voice. |
| LoLvl | LoLvl | Output level of the input-edge-divided low voice. |

Displayed knob values are integers. Internally, ordinary 0–100 controls become
normalized fractions; Speed is special because its descriptor maximum is 1000.
Mult and Div are discrete selectors with raw values 0–7, displayed as 1×–8× and
1/1–1/8. Their audio values follow the Arpoid Direction convention (displayed
value times 0.01).

### Constants and build macros

In `pll_dsp.h`:

- `TP_SR` is the sample rate, 44,100 samples/second. `TP_INV_SR` is its
  reciprocal, used to advance VCO phase without a divide in the audio loop.
- `TP_MIN_HZ` and `TP_MAX_HZ` are the VCO's hard frequency rails: 0 and 5,400 Hz.
- `TP_TWO_PI` is $2\pi$, used to turn loop bandwidth in hertz into angular
  frequency. `TP_DC_POLE` is the coefficient of the output DC-blocking filter.
- `TP_PRAGMA` and `TP_INLINE` ask TI's compiler to keep tiny DSP helpers inline;
  an outlined call from the audio function is unsafe for this ZDL runtime.

In `pll.c`:

- `PLL_AUDIO_FUNC` names the entry point that the builder exports as
  `Fx_SFX_PLL`. `TP_SECTION` places that function in the required `.audio`
  section.
- `ZDL_PTR` converts the firmware's 32-bit context words into pointers.
  `TP_MAGIC` and `TP_VERSION` identify the saved per-instance state layout;
  changing that layout requires a version bump. The current state version is 7.

### Saved PLL state

`PLLState` lives in the firmware-provided per-effect arena. It is separate
for each instance in the effects chain:

- `magic`, `version`, `initialized`: detect an uninitialized or older state and
  initialize it safely.
- `inputHigh`: remembers whether the input is above its positive Schmitt
  threshold. Rising and falling Schmitt transitions clock the low divider;
  only rising transitions send UP edges to the PLL detector.
- `up`, `down`: PFD latches. One remains set after its edge until the other edge
  arrives; their difference is the signed phase/frequency-detector output.
- `feedbackCount`, `multiplier`: count master-VCO cycles and pass one PFD
  feedback edge every N cycles. Mult is clamped to 1–8 and resets this count.
- `phase`: master-VCO phase, in cycles from 0 to 1; wrapping creates a high-voice
  edge. `dividerPhase` advances only from input crossings and creates the low voice.
- `integrator`: accumulated PI frequency correction; the removed P/I/V gain
  controls are fixed at 50, giving unity trims.
- `frequency`: the current bounded VCO frequency in hertz.
- `dcInput`, `dcOutput`: previous input/output samples for the one-pole DC
  blocker after the square VCO.

### Variables in the audio functions

In `Fx_SFX_PLL` (`pll.c`):

- `ctx` is the firmware context array. `params` points to the effect's parameter
  slots; `fxBuf` points to eight left samples followed by eight right samples.
- `magicSrc` / `magicDst` preserve Zoom's required context “magic shuttle”.
- `desc`, `base`, and `end` locate and bounds-check this instance's state arena;
  `st` points to the validated `PLLState`.
- `centerHz` is fixed at the Center=0 mapping, 55 Hz. `speed`, `damping`, and
  `level` are normalized controls; `multKnob` and `divKnob` decode the discrete
  Mult/Div selector values. `highLevel` and `lowLevel` independently scale the
  two voices. `multiplier` and `divider` are integers 1–8.
  `threshold` is fixed at 0.0001, the old Input=0 setting.
- `bandwidth` is the loop natural frequency; `omega` is $2\pi$ times that
  frequency; `zeta` is the damping ratio mapped from the full Damp 0–100 range.
  `kp` and `ki` are the P and I coefficients with gains fixed at 50 (unity).
  Both PI coefficients have already been multiplied by Mult N.
- `f` counts through the eight samples in the current firmware audio block.

In `tp_process` (`pll_dsp.h`), called once per sample:

- `s` is the persistent state. `inL` is the reference sample; `inR` is accepted
  to match the stereo audio interface but is intentionally unused by the PLL.
- `inputThreshold`, `centerHz`, `kp`, `ki`, `vcoGain`, `dividerHalfRecip`,
  `level`, `highLevel` and `lowLevel` are the already-decoded controls and
  calculations. `outL` / `outR` receive the mono wet
  oscillator output (full-wet routing).
- `inputEdge` is the rising Schmitt edge for the PFD; `inputCrossing` is either
  the rising or falling Schmitt edge for the low divider. `vcoEdge` is a master
  VCO wrap. `nextPhase` is the next high-voice phase. `pd` is +1 while UP is
  pending, −1 while DOWN is pending, and 0 when neither/both are pending.
- Each master VCO wrap increments `feedbackCount`; only every Mult-th wrap sets
  the PFD's DOWN latch. `dividerHalfRecip` is 0.5/Div; at each of the two input
  crossings per cycle it advances the low voice phase by that amount. This is
  why the low voice follows input pitch without gliding with PLL Speed.
- `candidate` is the proposed next integrator value. `correction` applies
  the fixed-unity VCO gain to P+I; `raw` is the proposed VCO frequency before its rails.
  `gainRecip`, `lowI`, and `highI` keep the integrator inside the safe frequency
  range without a runtime division. `highVoice` and `lowVoice` are the two ±1
  square waves; `voices` is their separately level-scaled average. `wet` is
  that mix after DC removal and shared Level, clamped to ±1.

The helper-function locals are short-lived working values: in `tp_exp2`, `n` is
the integer exponent, `t` the fractional part in natural-log units, `p` the
polynomial approximation, and `scale` the bit-built power-of-two multiplier.
In `tp_recip`, `v` holds the input's float bits and `y` is the refined reciprocal.
In `tp_center_hz`, `knob` is normalized Center; in `tp_internal_speed`, `knob`
is normalized Speed and maps it to 0–1000. `tp_bandwidth_hz` converts that to
the loop-frequency formula's scale. In `tp_damping_ratio`, `knob` is normalized
Damp and is mapped linearly across the full range. `tp_ratio_from_knob` converts
Mult/Div audio selector values (displayed raw value × 0.01) into integer values
1–8.
In `tp_init`, `s` is the state to reset and `centerHz` is the
initial VCO frequency.

### Functions

In `pll_dsp.h`:

- `tp_exp2(x)`: approximate $2^x$ with scalar arithmetic. Used for Center's
  logarithmic frequency mapping without calling the DSP math library.
- `tp_init(s, centerHz)`: clears PFD history, PI correction and output-filter
  history, then starts the VCO at Center.
- `tp_recip(x)`: estimates $1/x$ with a bit-derived seed and Newton refinements;
  used by anti-windup bounds without a runtime divide helper.
- `tp_center_hz(knob)`: maps Center 0–1 logarithmically to 55–880 Hz.
- `tp_bandwidth_hz(knob)`: maps normalized Speed to the loop natural frequency,
  from 0.5 Hz at Speed 0 to 750.5 Hz at Speed 1000.
- `tp_internal_speed(knob)`: maps normalized Speed linearly to the requested
  internal range 0–1000.
- `tp_damping_ratio(knob)`: maps the full normalized Damp range linearly to the
  damping ratio; Damp=32 gives approximately 0.707.
- `tp_ratio_from_knob(knob)`: quantizes either normalized Mult or Div selector
  into one of eight integer values.
- `tp_process(...)`: one sample of the complete loop: detect input/VCO edges,
  count master wraps for multiplied feedback, clock the low voice directly from
  both-polarity input crossings, update PFD latches, run the PI filter with rail
  anti-windup, advance both phases, apply separate voice levels and shared Level,
  remove output DC, and write full-wet stereo output.

In `pll.c`:

- `Fx_SFX_PLL(ctx)` (expanded from `PLL_AUDIO_FUNC`) is the firmware
  audio entry. It copies the magic shuttle, validates/initializes state, reads
  controls, computes loop coefficients once per block, and calls `tp_process`
  for each of eight samples. When Zoom bypasses the effect it freezes the loop
  and clears pending PFD latches.

The file names in the PLL folder mirror this split: `build.py` compiles and
links the ZDL; `manifest.json` declares the pedal controls and identity; the
preview renderer compiles the same DSP header for desktop audio; the regression
tests check frequency lock, high-Speed bounds and wrapper/preview agreement.

## Accuracy and limits

Tests feed known periodic references through the actual C loop and verify that
the generated VCO settles to expected frequencies across E2–A5-ish examples,
starting from the fixed 55 Hz center and using Speed/Damping settings. High-Speed tests check that
frequency remains bounded and audio stays finite. These checks validate the
implementation; they do not claim every guitar signal will lock correctly.

- This is an **edge-PFD PLL**, not an analog circuit simulation. The input
  detector is sampled at 44.1 kHz; there is no sub-sample crossing interpolation.
  The fixed low threshold, noise, harmonics, cycle slips and chords can cause
  jitter or lock to an unintended periodic component.
- The loop has a designed second-order PI response and adjustable damping, but
  sampled PFD pulse widths, hard VCO rails and the guitar edge detector alter
  the ideal small-signal response. Speed 1000 is an extreme experiment; actual
  capture/stability limits have not been measured on the pedal.
- The square VCO is intentionally rich in harmonics and aliases near the upper
  frequency limit. The loop compares its phase-accumulator edge, not its audio
  spectrum; output DC is removed by the 20 Hz blocker.
- Detection observes only the left channel; output is full-wet dual mono. There
  is no AGC, input low-pass, lock detector or silence gate.
- Zoom bypass stops updating the loop; re-enable clears stale PFD latches. An
  analog PLL that remained powered would continue running while bypassed.

## Build and preview

This is PLL **version 3.41**. Mult/Div create two voices from one PLL, and
HiLvl/LoLvl control them independently. Center and the three PI/VCO gains are
fixed internally. Mult/Div are eight-step selectors with one pedal position per
choice. **Re-dial and save PLL's controls after reinstalling**; the removed
controls changed the parameter slots.

Current identity: SFX category, GID 7, FXID 486 (`0x01E6`). Category routing is
not hardware-tested. Older Delay builds have a different firmware patch ID;
editor aliases do not migrate it or the old control layout. Follow the
[backup, replacement and patch upgrade procedure](../../../docs/INSTALLING-ZDLS.md#upgrading-from-the-all-delay-pack).

```bash
python3 -B build_all.py pll
python3 -B tools/audio_preview/preview.py render pll previews/audio/dry_guitar.wav preview-output/pll.wav --tail 0
python3 -B tools/audio_preview/preview.py render pll previews/audio/dry_guitar.wav preview-output/pll-wet.wav --set speed=1000 --set damping=32 --set hilvl=100 --set lolvl=100
python3 -B tools/audio_preview/preview.py render pll previews/audio/dry_guitar.wav preview-output/pll-4x-2down.wav --set speed=500 --set mult=3 --set div=1 --set level=45 --set hilvl=100 --set lolvl=70 --tail 0
```

Mult and Div each select one of eight discrete choices. Preview values are the
selector's raw option number 0–7: Mult 3 is 4× and Div 1 is 1/2. The master VCO
starts at fixed Center=0 (55 Hz); the P/I/V gains are fixed at 50 (unity). The
lower voice comes directly from input edges and should not glide when Speed
changes. HiLvl and LoLvl scale the two voices separately before shared Level.

Speed sweeps the internal response from 0.5 to 750.5 Hz. Sweep it from 0 to
1000 with Damping at its default, then change one loop parameter at a time.

Builds `dist/PLL.ZDL`, its cover and Patch Editor data. Desktop preview
compiles the same portable C core; it needs `cc`, NumPy, SciPy and SoundFile,
not TI tools. Other WAV rates are resampled through 44.1 kHz. Use low listening
volume. No output normalization is applied.


