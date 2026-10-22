/* PLL digital analogue model: PFD -> active PI loop filter -> VCO.
 * Integer-N Ratio divides VCO feedback edges, so locked output is N*input.
 * Portable scalar core shared by the Zoom entry point and host renderer.
 * No math-library calls, tables, division or dynamic storage.
 */
#ifndef PLL_DSP_H
#define PLL_DSP_H
#include <stdint.h>

#define TP_SR 44100.0f
#define TP_INV_SR (1.0f / TP_SR)
// #define TP_MIN_HZ 1.0f
#define TP_MIN_HZ 0.0f
#define TP_MAX_HZ 5400.0f
#define TP_TWO_PI 6.28318530718f
#define TP_DC_POLE 0.99715454f

typedef struct PLLState {
    uint32_t magic, version, initialized;
    uint32_t inputHigh, up, down;
    uint32_t feedbackCount, multiplier;
    float phase, dividerPhase, integrator, frequency;
    float dcInput, dcOutput;
} PLLState;

#ifdef __TI_COMPILER_VERSION__
#define TP_PRAGMA(x) _Pragma(#x)
#define TP_INLINE(f) TP_PRAGMA(FUNC_ALWAYS_INLINE(f))
#else
#define TP_INLINE(f)
#endif


TP_INLINE(tp_exp2)
static inline float tp_exp2(float x)
{
    int n = (int)x;
    if ((float)n > x) n--;
    float t = (x - (float)n) * 0.69314718056f;
    float p = 1.0f + t * (1.0f + t * (0.5f + t * (0.166666667f + t *
        (0.041666667f + t * (0.008333333f + t * 0.001388889f)))));
    union { float f; uint32_t u; } scale;
    scale.u = (uint32_t)(n + 127) << 23;
    return p * scale.f;
}

TP_INLINE(tp_init)
static inline void tp_init(PLLState *s, float centerHz)
{
    s->inputHigh = s->up = s->down = 0u;
    s->feedbackCount = 0u;
    s->multiplier = 1u;
    s->phase = s->dividerPhase = 0.0f;
    s->integrator = 0.0f;
    s->frequency = centerHz;
    s->dcInput = 1.0f;
    s->dcOutput = 0.0f;
}

TP_INLINE(tp_recip)
static inline float tp_recip(float x)
{
    union { float f; uint32_t u; } v, y;
    v.f = x;
    y.u = 0x7ef311c3u - v.u;
    y.f *= 2.0f - x * y.f;
    y.f *= 2.0f - x * y.f;
    y.f *= 2.0f - x * y.f;
    return y.f;
}

/* Center knob 0..1 spans four octaves, 55..880 Hz. */
TP_INLINE(tp_center_hz)
static inline float tp_center_hz(float knob)
{
    return 55.0f * tp_exp2(4.0f * knob);
}

/* Speed UI 0..1000 maps linearly to internal speed 0..1000. */
TP_INLINE(tp_internal_speed)
static inline float tp_internal_speed(float knob)
{
    return 1000.0f * knob;
}

TP_INLINE(tp_bandwidth_hz)
static inline float tp_bandwidth_hz(float knob)
{
    float internalSpeed = tp_internal_speed(knob);
    float normalizedSpeed = internalSpeed * 0.01f;
    return 0.5f + 7.5f * normalizedSpeed * normalizedSpeed;
}

TP_INLINE(tp_damping_ratio)
static inline float tp_damping_ratio(float knob)
{
    return 0.1f + 1.8972087f * knob;
}

/* Discrete selector audio values are displayed selector values times 0.01;
 * decode raw selector values 0..7 as integer ratios 1..8. */
TP_INLINE(tp_ratio_from_knob)
static inline uint32_t tp_ratio_from_knob(float knob)
{
    int choice = (int)(knob * 100.0f + 0.5f);
    if (choice < 0) choice = 0;
    if (choice > 7) choice = 7;
    return (uint32_t)choice + 1u;
}

TP_INLINE(tp_process)
static inline void tp_process(PLLState *s, float inL, float inR,
                             float inputThreshold, float centerHz,
                             float kp, float ki, float vcoGain,
                             uint32_t multiplier, float dividerHalfRecip, float level,
                             float highLevel, float lowLevel,
                             float *outL, float *outR)
{
    if (multiplier < 1u) multiplier = 1u;
    if (multiplier > 8u) multiplier = 8u;
    if (multiplier != s->multiplier) {
        s->multiplier = multiplier;
        s->feedbackCount = 0u;
        s->down = 0u;
    }
    uint32_t inputEdge = 0u, inputCrossing = 0u;
    if (!s->inputHigh && inL > inputThreshold) {
        inputEdge = 1u;
        inputCrossing = 1u;
        s->inputHigh = 1u;
    } else if (s->inputHigh && inL <= -inputThreshold) {
        inputCrossing = 1u;
        s->inputHigh = 0u;
    }
    /* Divide the conditioned input's both-polarity Schmitt crossings, not
     * the smoothed PLL VCO. Thus the lower voice tracks edges immediately
     * and does not glide with PI loop Speed. Two crossings per input cycle,
     * each advancing 0.5/N phase, produce one output cycle per N input cycles. */
    if (inputCrossing) {
        s->dividerPhase += dividerHalfRecip;
        if (s->dividerPhase >= 1.0f) s->dividerPhase -= 1.0f;
    }

    /* Edge-triggered UP/DOWN latches form a phase-frequency detector. The
     * pulse width carries signed phase error; an unmatched latch indicates
     * frequency error while acquiring or after a cycle slip. */
    if (inputEdge) s->up = 1u;
    float nextPhase = s->phase + s->frequency * TP_INV_SR;
    uint32_t vcoEdge = 0u;
    if (nextPhase >= 1.0f) {
        nextPhase -= 1.0f;
        vcoEdge = 1u;
    }
    /* Integer-N multiplier in the feedback path: compare one feedback edge
     * for every N VCO cycles, while the audio VCO itself runs at the high rate. */
    if (vcoEdge) {
        s->feedbackCount++;
        if (s->feedbackCount >= multiplier) {
            s->feedbackCount = 0u;
            s->down = 1u;
        }
    }
    if (s->up && s->down) s->up = s->down = 0u;
    float pd = (float)s->up - (float)s->down;

    /* Active PI loop filter, with second-order coefficients derived from the
     * selected damping and natural frequency. */
    float candidate = s->integrator + ki * pd * TP_INV_SR;
    float correction = vcoGain * (candidate + kp * pd);
    float raw = centerHz + correction;
    if ((raw > TP_MAX_HZ && pd > 0.0f) || (raw < TP_MIN_HZ && pd < 0.0f))
        candidate = s->integrator;
    float gainRecip = tp_recip(vcoGain);
    float lowI = (TP_MIN_HZ - centerHz) * gainRecip;
    float highI = (TP_MAX_HZ - centerHz) * gainRecip;
    if (candidate < lowI) candidate = lowI;
    if (candidate > highI) candidate = highI;
    s->integrator = candidate;
    raw = centerHz + vcoGain * (s->integrator + kp * pd);
    s->frequency = raw < TP_MIN_HZ ? TP_MIN_HZ : (raw > TP_MAX_HZ ? TP_MAX_HZ : raw);
    s->phase = nextPhase;
    float highVoice = s->phase < 0.5f ? 1.0f : -1.0f;
    /* Input's rising Schmitt edge advances dividerPhase by half a cycle.
     * Invert the comparator polarity so that edge aligns the sub voice's
     * rising edge with the master VCO's rising edge when locked at 1:1. */
    float lowVoice = s->dividerPhase < 0.5f ? -1.0f : 1.0f;
    float voices = 0.5f * (highLevel * highVoice + lowLevel * lowVoice);
    s->dcOutput = voices - s->dcInput + TP_DC_POLE * s->dcOutput;
    s->dcInput = voices;
    float wet = level * s->dcOutput;
    if (wet > 1.0f) wet = 1.0f;
    else if (wet < -1.0f) wet = -1.0f;
    *outL = wet;
    *outR = wet;
}
#endif /* PLL_DSP_H */
