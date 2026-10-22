/* PLL: digital phase-frequency detector -> PI filter -> VCO. */
#include <stdint.h>
#include "../../airwindows/common/zoom_params.h"
#include "pll_params.h"
#include "pll_dsp.h"

#ifndef PLL_AUDIO_FUNC
#define PLL_AUDIO_FUNC Fx_SFX_PLL
#endif
#define TP_SECTION_PRAGMA(x) _Pragma(#x)
#define TP_SECTION(f) TP_SECTION_PRAGMA(CODE_SECTION(f, ".audio"))
TP_SECTION(PLL_AUDIO_FUNC)

#define ZDL_PTR(type, word) ((type)(uintptr_t)(word))
#define TP_MAGIC 0x54504c4cu
#define TP_VERSION 7u

void PLL_AUDIO_FUNC(unsigned int *ctx)
{
    float *params = ZDL_PTR(float *, ctx[1]);
    float *fxBuf = ZDL_PTR(float *, ctx[5]);
    unsigned int *magicSrc = ZDL_PTR(unsigned int *, ctx[12]);
    unsigned int *magicDst = ZDL_PTR(unsigned int *, *(unsigned int *)ZDL_PTR(unsigned int *, ctx[11]));
    *magicDst = *magicSrc;

    volatile unsigned int *desc = ZDL_PTR(volatile unsigned int *, ctx[3]);
    if (!desc) return;
    uintptr_t base = (uintptr_t)desc[0], end = (uintptr_t)desc[1];
    if (!base || end <= base || (base & 3u)) return;
    if (end - base < (uintptr_t)sizeof(PLLState)) return;
    PLLState *st = (PLLState *)base;
    float centerHz = tp_center_hz(0.0f); /* Removed Center knob is fixed at UI 0. */
    if (st->magic != TP_MAGIC || st->version != TP_VERSION || !st->initialized) {
        tp_init(st, centerHz);
        st->magic = TP_MAGIC;
        st->version = TP_VERSION;
        st->initialized = 1u;
    }
    if (params[0] < 0.5f) {
        /* Freeze the loop while bypassed and clear phase-detector latches so
         * stale UP/DOWN pulses are not replayed on re-enable. */
        st->up = st->down = 0u;
        return;
    }

    float speed = zoom_param_norm01(params[PLL_SPEED_SLOT], PLL_SPEED_DEFAULT_NORM);
    float damping = zoom_param_norm01(params[PLL_DAMPING_SLOT], PLL_DAMPING_DEFAULT_NORM);
    /* Removed P/I/V gain knobs are fixed at UI 50, i.e. unity trims. */
    float pGain = 0.5f;
    float iGain = 0.5f;
    float vcoGainNorm = 0.5f;
    float multKnob = zoom_param_norm01(params[PLL_MULT_SLOT], PLL_MULT_DEFAULT_NORM);
    float divKnob = zoom_param_norm01(params[PLL_DIV_SLOT], PLL_DIV_DEFAULT_NORM);
    float level = zoom_param_norm01(params[PLL_LEVEL_SLOT], PLL_LEVEL_DEFAULT_NORM);
    float highLevel = zoom_param_norm01(params[PLL_HILVL_SLOT], PLL_HILVL_DEFAULT_NORM);
    float lowLevel = zoom_param_norm01(params[PLL_LOLVL_SLOT], PLL_LOLVL_DEFAULT_NORM);
    uint32_t multiplier = tp_ratio_from_knob(multKnob);
    uint32_t divider = tp_ratio_from_knob(divKnob);
    float dividerHalfRecip = 0.5f * tp_recip((float)divider);
    float threshold = 0.0001f;
    float bandwidth = tp_bandwidth_hz(speed);
    float omega = TP_TWO_PI * bandwidth;
    float zeta = tp_damping_ratio(damping);
    /* Integer-N feedback division reduces loop gain by N; scale both PI
     * paths by N as the first-order compensation for similar loop dynamics. */
    float kp = 2.0f * zeta * omega * (2.0f * pGain) * (float)multiplier;
    float ki = omega * omega * (2.0f * iGain) * (float)multiplier;
    float vcoGain = 0.1f + 1.8f * vcoGainNorm;

    int f;
    for (f = 0; f < 8; f++) {
        tp_process(st, fxBuf[f], fxBuf[f + 8], threshold, centerHz,
                   kp, ki, vcoGain, multiplier, dividerHalfRecip, level,
                   highLevel, lowLevel,
               &fxBuf[f], &fxBuf[f + 8]);
    }
}

