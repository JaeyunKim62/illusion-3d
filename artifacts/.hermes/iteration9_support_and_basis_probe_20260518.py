from pathlib import Path
from PIL import Image
import numpy as np, json, math

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'algorithm-exploration' / 'iteration-9-support-and-basis-probe-20260518.json'
REF = ROOT / 'artifacts' / 'reference-image'

W,H = 160,120
THR = 8

def load_mask(name):
    img = Image.open(REF/name).convert('RGBA').resize((W,H), Image.Resampling.LANCZOS)
    arr=np.array(img)
    alpha=arr[...,3]
    rgb=arr[...,:3].astype(np.float32)/255.0
    # include non-white opaque pixels for jpg-like inputs too
    nonwhite=np.linalg.norm(rgb-1.0, axis=2)>0.08
    m=(alpha>THR) & nonwhite
    return m

def shift(mask, dx=0, dy=0):
    out=np.zeros_like(mask)
    ys,xs=np.where(mask)
    nx=xs+dx; ny=ys+dy
    keep=(nx>=0)&(nx<W)&(ny>=0)&(ny<H)
    out[ny[keep], nx[keep]]=True
    return out

def iou(a,b):
    u=np.logical_or(a,b).sum(); inter=np.logical_and(a,b).sum()
    return float(inter/u) if u else 1.0

def support_metrics(base,target):
    missing=np.logical_and(target, ~base).sum()
    erase=np.logical_and(base, ~target).sum()
    target_count=target.sum(); base_count=base.sum()
    sym=np.logical_xor(base,target).sum()
    union=np.logical_or(base,target).sum()
    return {
        'target_pixels': int(target_count),
        'base_pixels': int(base_count),
        'iou': iou(base,target),
        'create_missing_pixels': int(missing),
        'create_missing_ratio_vs_target': float(missing/target_count) if target_count else 0.0,
        'erase_or_background_cheat_pixels': int(erase),
        'erase_ratio_vs_base': float(erase/base_count) if base_count else 0.0,
        'support_symmetric_diff_ratio': float(sym/union) if union else 0.0,
        'color_only_pass_missing_le_1pct': bool((missing/target_count if target_count else 0.0) <= 0.01),
        'geometry_needed_if_no_opacity_gate': bool((missing/target_count if target_count else 0.0) > 0.01 or (erase/base_count if base_count else 0.0) > 0.01)
    }

def weights(kind, degs):
    vals=[]
    for deg in degs:
        t=deg/90.0
        rad=math.radians(deg)
        if kind=='cosine_s1':
            f=max(0, math.cos(rad)); r=max(0, math.sin(rad)); s=f+r
            w=r/s if s else 0
        elif kind=='cosine_s2':
            f=max(0, math.cos(rad))**2; r=max(0, math.sin(rad))**2; s=f+r
            w=r/s if s else 0
        elif kind=='cosine_s8':
            f=max(0, math.cos(rad))**8; r=max(0, math.sin(rad))**8; s=f+r
            w=r/s if s else 0
        elif kind=='smoothstep':
            w=t*t*(3-2*t)
        elif kind=='smootherstep':
            w=t*t*t*(t*(t*6-15)+10)
        elif kind=='linear':
            w=t
        vals.append(w)
    return np.array(vals, dtype=float)

def basis_metrics(kind, step=5):
    degs=np.arange(0,91,step)
    w=weights(kind,degs)
    lin=degs/90.0
    jumps=np.abs(np.diff(w))
    accel=np.abs(w[2:]-2*w[1:-1]+w[:-2]) if len(w)>2 else np.array([0.0])
    return {
        'kind': kind,
        'endpoint_leak_front': float(w[0]),
        'endpoint_leak_right': float(1-w[-1]),
        'linear_path_rmse': float(np.sqrt(np.mean((w-lin)**2))),
        'max_5deg_weight_jump': float(jumps.max()) if len(jumps) else 0.0,
        'max_5deg_accel': float(accel.max()) if len(accel) else 0.0,
        'mid_45_weight': float(w[len(w)//2]),
        'monotone': bool(np.all(np.diff(w)>=-1e-9))
    }

def main():
    masks={name: load_mask(name) for name in ['goose.png','nubzuki.png','cake.png','phoenix.png','kumdori.png']}
    shift_tests={}
    for name,mask in masks.items():
        tests=[]
        for dx in [1,2,4,8,12]:
            tests.append({'shift':'right_%dpx'%dx, **support_metrics(mask, shift(mask, dx=dx))})
        for dy in [1,2,4,8]:
            tests.append({'shift':'down_%dpx'%dy, **support_metrics(mask, shift(mask, dy=dy))})
        shift_tests[name]=tests

    # Endpoint support incompatibility if someone tries to morph one asset into another by color only at a fixed view.
    pair_tests=[]
    pairs=[('goose.png','nubzuki.png'),('goose.png','cake.png'),('goose.png','phoenix.png'),('goose.png','kumdori.png')]
    for a,b in pairs:
        pair_tests.append({'base':a,'target':b, **support_metrics(masks[a], masks[b])})

    basis=[basis_metrics(k) for k in ['linear','smoothstep','smootherstep','cosine_s1','cosine_s2','cosine_s8']]
    result={
        'notes':[
            'Color-only/material-only can recolor existing projected support but cannot create target foreground outside support.',
            'If erasing existing support requires alpha-to-zero/background painting, classify as opacity-gate risk, not pure color.',
            'Shift tests use actual reference alpha/non-white masks resized to 160x120; they are a necessary-condition proxy, not browser render.'
        ],
        'support_shift_tests': shift_tests,
        'fixed_view_asset_support_pair_tests': pair_tests,
        'directional_weight_basis_metrics': basis,
        'recommended_basis_rule':'Prefer monotone endpoint-exact low-pop path such as cosine_s1 or smootherstep; reject cosine_s8-like sharp lobes unless pop metric is explicitly acceptable.',
        'morph_decision_rule':{
            'color_only_pass':'missing_ratio_vs_target <= 0.01 and erase_ratio_vs_base <= 0.01',
            'micro_displacement_candidate':'support diff mostly explained by <=2-4 px boundary shift and canonical views keep delta=0',
            'geometry_needed':'missing or erase ratio > 0.01, especially for >=4 px silhouette shifts or different asset supports',
            'forbidden_shortcut':'do not solve erase by view-dependent alpha-to-zero or background-colored projection-only points'
        }
    }
    OUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(OUT)

if __name__=='__main__':
    main()
