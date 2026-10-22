"""Audited release selectors; raw ranges preserve the existing patch ABI.

Mode thresholds use float32 UI*0.01, matching shared edit handlers, then the
comparisons in the DSP. Do not infer discrete controls from small max alone.
"""
import struct

def f32(v): return struct.unpack('<f',struct.pack('<f',v))[0]
def normalized(raw): return f32(raw*f32(.01))
def ladder(raw,limits): return sum(normalized(raw)>=f32(x) for x in limits)
def groups(labels, classify, maximum=100):
    result=[]
    for raw in range(maximum+1):
        label=labels[classify(raw)]
        if not result or result[-1]['label']!=label:
            result.append({'label':label,'from':raw,'to':raw,'value':raw})
        else: result[-1]['to']=raw
    for g in result: g['value']=(g['from']+g['to'])//2
    return result

SELECTORS={
 'PLL':{
     'Mult':groups(['1x','2x','3x','4x','5x','6x','7x','8x'],lambda r:r,7),
     'Div':groups(['1/1','1/2','1/3','1/4','1/5','1/6','1/7','1/8'],lambda r:r,7),
 },
}
def attach_selectors(effect):
    for p in effect['params']:
        choices=SELECTORS.get(effect['name'],{}).get(p['name'])
        if choices and choices[-1]['to']==p['max']:
            p['choices']=choices
    return effect

def pedal_label(label):
    return {'Release':'Rels', 'Stomp':'Stmp'}.get(label,label)

def pedal_label_c(manifest):
    """Stock GetString ABI: A4=integer value, B4=destination; return length.

    Values use at most five ASCII chars to fit a pedal column; the copy is
    bounded to the stock eight-byte string buffer. Enabled for release builds
    after the Stasis hardware confirmation.
    """
    import json
    lines=[]
    for i,p in enumerate(manifest['params']):
        choices=SELECTORS.get(manifest['effect_name'],{}).get(p['name'])
        if not choices: continue
        if choices[-1]['to']!=p['max']: raise ValueError('selector range mismatch')
        lines += [f'int ZDL_GetLabel_{i}(unsigned int value, char *out) {{',
                  '    const char *s; int i;']
        for j,c in enumerate(choices):
            label=pedal_label(c['label'])
            assert len(label.encode('ascii'))<=5
            if j==len(choices)-1: prefix='else'
            else: prefix=('if' if j==0 else 'else if')+f' (value <= {c["to"]}u)'
            lines.append(f'    {prefix} s = {json.dumps(label)};')
        lines += ['    for (i=0; i<7; ++i) { out[i]=s[i]; if (!s[i]) return i; }',
                  '    out[7]=0; return 7;', '}']
    return '\n'.join(lines)
