# fxid Registry

`fxid` is the 16-bit effect identity baked into every ZDL.  Two effects
with the same `fxid` (and the same `gid`) are treated as the same effect by
the Zoom firmware, which can cause silent overwrite or a freeze on load.

## Rules

- Stock effects occupy fxid **0 – 384** (0x000 – 0x180). Never use these.
- Community/custom effects use fxid **400 – 999**. Pick an unused value below.
- Diagnostic/hardware-probe effects share the 400–999 space but are never
  loaded alongside release effects, so probe collisions are low-risk during
  development. Keep them out of `dist/` and avoid reusing a release fxid for
  a probe.
- The linker emits a warning for fxid ≤ 384 (reserved range).
- If two release effects collide (same `fxid` AND same `gid`), fix one before
  shipping. Use `grep -r '"fxid"' src/` to audit.

## gid → category mapping

| gid | Category |
|-----|----------|
| 1   | Dynamics |
| 2   | Filter   |
| 3   | Drive    |
| 4   | Amp      |
| 5   | Cab      |
| 6   | Modulation |
| 7   | SFX / Special |
| 8   | Delay    |
| 9   | Reverb   |

## Current registry

### Release effects

| fxid | gid | effect_name | File | Notes |
|------|-----|-------------|------|-------|
| 400 | 2 | GAIN | `src/airwindows/gain` | Minimal smoke-test / template |
| 401 | 2 | PurestDr | `src/airwindows/purestdrive` | |
| 402 | 2 | TapeHack | `src/airwindows/tapehack` | |
| 403 | 3 | ToTape9 | `src/airwindows/totape9` | Drive category; install a stock Drive effect too |
| 404 | 6 | StChorus | `src/airwindows/stereochorus` | |
| 405 | 9 | VerbTiny | `src/airwindows/verbtiny` | Hardware unverified |
| 406 | 7 | ToVinyl4 | `src/airwindows/tovinyl4` | Diagnostic; not in dist/ |
| 408 | 9 | Galactic | `src/airwindows/galactic` | Hardware unverified |
| 409 | 8 | TapeEcho4 | `src/airwindows/tapeecho4` | Ships as TEcho4.ZDL |
| 410 | 1 | OTT | `src/custom/ott` | Hardware unverified |

### Hardware probe effects (not in dist/)

These share the fxid space during development. Several have intentional
collisions because only one probe variant is loaded at a time — but
note the warnings below.

| fxid | gid | effect_name | File | Collision warning |
|------|-----|-------------|------|-------------------|
| 400 | 2 | HELLO | `src/airwindows/hello` | Collides with GAIN (same fxid+gid); never load both |
| 405 | 2 | CtxMap | `src/hardware_probes/ctxmap` | Different gid from VerbTiny; still avoid loading together |
| 406 | 2 | ParamTap | `src/hardware_probes/paramtap` | Different gid from ToVinyl4 |
| 407 | 2 | CtxGate | `src/hardware_probes/ctxgate` | **Same fxid+gid as InitProbe** |
| 407 | 2 | InitProbe | `src/hardware_probes/initprobe` | **Same fxid+gid as CtxGate** |
| 408 | 2 | CtxNib | `src/hardware_probes/ctxnib` | Different gid from Galactic |
| 409 | 2 | StatePing | `src/hardware_probes/stateping` | Different gid from TapeEcho4 |
| 410 | 2 | SyncProbe | `src/hardware_probes/syncprobe` | Different gid from OTT |
| 413 | 2 | StateIso | `src/hardware_probes/stateiso` | |
| 414 | 2 | SyncPrV2 | `src/hardware_probes/syncprobv2` | |
| 415 | 2 | BpmHunt | `src/hardware_probes/bpmhunt` | **Same fxid+gid as StateComb** |
| 415 | 2 | StateComb | `src/hardware_probes/statecomb` | **Same fxid+gid as BpmHunt** |
| 416 | 2 | DescComb | `src/hardware_probes/desccomb` | **Same fxid+gid as SyncCalc + SyncPrV3** |
| 416 | 2 | SyncCalc | `src/hardware_probes/synccalc` | **Same fxid+gid as DescComb + SyncPrV3** |
| 416 | 2 | SyncPrV3 | `src/hardware_probes/syncprobv3` | **Same fxid+gid as DescComb + SyncCalc** |
| 417 | 2 | Dsz512K | `src/hardware_probes/descsize` | |
| 426 | 2 | DescIso | `src/hardware_probes/desciso` | |

## Next available fxid for a new release effect

**427** (first unused above the current probe high-water mark).

When you claim a new fxid, add it to this table in the same PR that adds the
`manifest.json`.
