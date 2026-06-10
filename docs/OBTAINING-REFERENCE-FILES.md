# Obtaining Reference Files

`stock_zdls/`, `firmware/`, and the TI manuals are not distributed in this
repository. They contain Zoom- and TI-copyrighted material. This doc explains
where to get each piece.

## Stock ZDL corpus (stock_zdls/)

The 830-file stock ZDL corpus is extracted from official Zoom MS-70CDR firmware.

1. Download MS-70CDR firmware 2.10 from Zoom's support site:
   https://zoomcorp.com/en/us/multi-effects/multistomp-pedals/ms-70cdr/ms-70cdr-support/
2. Install [Zoom Effect Manager](https://zoomeffectmanager.com/en/download/) 2.3.3+.
3. Open Zoom Effect Manager, connect your pedal, and use it to extract effects
   to a local folder; or use `Zoom-Firmware-Editor` (available separately) to
   unpack the firmware archive and find the ZDL files inside.
4. Place the resulting `.ZDL` files in `stock_zdls/` at the repo root.

The build toolchain (`build/linker.py`) does **not** read `stock_zdls/` at
build time. The corpus is used only by the analysis scripts in `build/` when
reverse-engineering ABI details.

## Firmware images (firmware/)

The raw firmware images (`Main.bin`, `boot.bin`, `FS.bin`, `Preset.bin`) come
from the same firmware download above. Unpack the `.zfp` archive (it is a ZIP)
and place the resulting `.bin` files inside `firmware/`.

The disassembly fragments in `firmware/extracted/` were produced by IDA Pro /
Ghidra from `Main.bin`. They are also not tracked; re-derive them from
`Main.bin` if needed.

## TI C6000 architecture manuals (docs/*.pdf)

The three PDFs previously in `docs/` are free-to-download TI publications.
Get them from https://www.ti.com by searching for:

| Filename | Document title / part number |
|---|---|
| `sprab89b.pdf` | *TMS320C6000 Assembly Language Tools User's Guide* (SPRAB89) |
| `sprui03f.pdf` | *TMS320C6000 Optimizing Compiler User's Guide* (SPRUI03) |
| `sprui04g.pdf` | *TMS320C6000 DSP CPU and Instruction Set Reference Guide* (SPRUI04) |

Download them to `docs/` — they are gitignored so they will not be committed.
