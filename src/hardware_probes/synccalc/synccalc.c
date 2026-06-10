/*
 * synccalc.c — v1, §4 algorithm validator.
 *
 * Calls the firmware's state[24] (= c00d4b40, a float-math utility per
 * the disassembly: ABSSP / CMPEQSP / RCPSP polynomial) directly from
 * the audio context. The Sync knob (0..15) selects A4 = float(idx+1)
 * so the call inputs vary across positions; B4 is always float(100.0).
 *
 * Two questions the user can answer by listening:
 *   1. Does state[24] return varying values for varying A4?
 *      Sweep Sync at fixed BPM — gain should change per position.
 *   2. Does state[24] consult tempo state?
 *      At a fixed Sync position, tap from 75 → 250 BPM.
 *      Gain change with tap = §4's "BPM folds in via state[24]" claim
 *      is correct. Constant gain = §4 is wrong about that.
 *
 * If state[24] is callable but pure math, BPM folds in elsewhere
 * (probably via the state[31] secondary table at 0xc009fe90 if it
 * actually exists and varies with tempo). v2 would probe that.
 */

#include <stdint.h>

#include "synccalc_params.h"

#pragma CODE_SECTION(Fx_FLT_SyncCalc, ".audio")

#define ZDL_PTR(type, word) ((type)(uintptr_t)(word))

/* Firmware function address for state[24]. Template-writer populates
 * every slot's state[24] callback with this. */
#define FW_STATE24_ADDR  0xc00d4b40u

typedef unsigned int (*fw_state_fn)(unsigned int a4, unsigned int b4);

void Fx_FLT_SyncCalc(unsigned int *ctx)
{
    float *params = ZDL_PTR(float *, ctx[1]);
    float *fxBuf  = ZDL_PTR(float *, ctx[5]);
    float *outBuf = ZDL_PTR(float *, ctx[6]);

    /* Preserve LineSel current-sample plumbing. */
    unsigned int *magicSrc = ZDL_PTR(unsigned int *, ctx[12]);
    unsigned int *magicDst = ZDL_PTR(unsigned int *, *(unsigned int *)ZDL_PTR(unsigned int *, ctx[11]));
    *magicDst = *magicSrc;

    /* Decode Sync knob 0..15 from the LineSel 0..~0.14 raw float. */
    float raw = params[SYNCCALC_SYNC_SLOT];
    if (raw < 0.0f) raw = -raw;
    if (raw > 1.0f) raw = 1.0f;
    int idx = (int)(raw * (15.0f / 0.14f));
    if (idx < 0) idx = 0;
    if (idx > 15) idx = 15;

    /* A4 = float(idx + 1) — non-zero so state[24]'s ABSSP/CMPEQSP-0
     * early-exit at the top of c00d4b40 doesn't fire. */
    union { float f; unsigned int u; } a4u;
    a4u.f = (float)(idx + 1);
    unsigned int a4_bits = a4u.u;

    /* B4 = float(100.0) = 0x42C80000. TAPEECH3's static trace shows
     * MVK B4,100 — integer 100, which as float is denormal ≈ 0 and
     * would also early-exit. Pass float(100.0) so the call body runs. */
    unsigned int b4_bits = 0x42C80000u;

    /* Direct call into firmware. state[24] is leaf math (no IO, no
     * peripheral access) so calling it from audio context is safe. */
    fw_state_fn fw_state24 = (fw_state_fn)FW_STATE24_ADDR;
    unsigned int y = fw_state24(a4_bits, b4_bits);

    /* Byte-sum gain — sensitive to changes in any byte of y. */
    unsigned int byte_sum =
        ((y >> 24) & 0xFFu) +
        ((y >> 16) & 0xFFu) +
        ((y >>  8) & 0xFFu) +
        ( y        & 0xFFu);
    float gain = (float)byte_sum * (1.0f / 510.0f);
    if (gain > 2.0f) gain = 2.0f;

    int i;
    for (i = 0; i < 16; i++) {
        outBuf[i] += fxBuf[i] * gain;
    }
}
