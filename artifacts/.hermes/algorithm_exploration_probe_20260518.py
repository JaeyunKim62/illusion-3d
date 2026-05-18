#!/usr/bin/env python3
"""Throwaway feasibility probe for algorithm-exploration-20260518.
Does not touch production source. Uses synthetic binary masks only."""
from __future__ import annotations
from collections import defaultdict
import json, math, random

W=64; H=48; D=64
random.seed(4792026)

def ellipse_mask(w,h,cx,cy,rx,ry,holes=()):
    s=set()
    for y in range(h):
        for x in range(w):
            if ((x-cx)/rx)**2 + ((y-cy)/ry)**2 <= 1:
                in_hole=False
                for hx,hy,hrx,hry in holes:
                    if ((x-hx)/hrx)**2 + ((y-hy)/hry)**2 <= 1:
                        in_hole=True; break
                if not in_hole: s.add((x,y))
    return s

def rect_mask(w,h,x0,y0,x1,y1):
    return {(x,y) for y in range(max(0,y0), min(h,y1)) for x in range(max(0,x0), min(w,x1))}

def iou(a,b):
    return len(a&b)/max(1,len(a|b))

def row_bins(mask):
    bins=defaultdict(list)
    for x,y in mask: bins[y].append(x)
    for y in bins: bins[y].sort()
    return bins

def row_policy(front, side, policy):
    F=row_bins(front); S=row_bins(side)
    points=[]
    coverF=defaultdict(set); coverS=defaultdict(set)
    duplicate_f=0; duplicate_s=0
    for y in range(H):
        xs=F.get(y,[]); zs=S.get(y,[])
        if not xs or not zs: continue
        if policy=='min': n=min(len(xs),len(zs)); pairs=list(zip(xs[:n], zs[:n]))
        elif policy=='max_reuse':
            n=max(len(xs),len(zs)); pairs=[]
            for i in range(n):
                pairs.append((xs[i%len(xs)], zs[i%len(zs)]))
                if i>=len(xs): duplicate_f+=1
                if i>=len(zs): duplicate_s+=1
        elif policy=='balanced_ot':
            # quantile matching with fractional capacity; materialized at max count, but chooses monotone indices.
            n=max(len(xs),len(zs)); pairs=[]
            for i in range(n):
                q=(i+0.5)/n
                xi=xs[min(len(xs)-1, int(q*len(xs)))]
                zi=zs[min(len(zs)-1, int(q*len(zs)))]
                pairs.append((xi,zi))
                if i>=len(xs): duplicate_f+=1
                if i>=len(zs): duplicate_s+=1
        else: raise ValueError(policy)
        for x,z in pairs:
            points.append((x,y,z)); coverF[y].add(x); coverS[y].add(z)
    projF={(x,y) for y,xs in coverF.items() for x in xs}
    projS={(z,y) for y,zs in coverS.items() for z in zs}
    return dict(policy=policy, points=len(points), front_iou=iou(front,projF), side_iou=iou(side,projS), front_coverage=len(projF)/max(1,len(front)), side_coverage=len(projS)/max(1,len(side)), duplicate_front=duplicate_f, duplicate_side=duplicate_s)

front = ellipse_mask(W,H,30,24,24,16, holes=[(22,20,4,3),(39,20,4,3)]) | rect_mask(W,H,44,28,58,33)
side = ellipse_mask(D,H,30,24,15,18) | rect_mask(D,H,8,18,22,26) | rect_mask(D,H,42,31,54,36)
row_results=[row_policy(front,side,p) for p in ['min','max_reuse','balanced_ot']]

# 3-view feasibility: exact visual hull for projections A(x,y), B(z,y), C(x,z).
def visual_hull(A,B,C,w=W,h=H,d=D):
    vox=[]
    for y in range(h):
        xs=[x for x in range(w) if (x,y) in A]
        zs=[z for z in range(d) if (z,y) in B]
        if not xs or not zs: continue
        for x in xs:
            for z in zs:
                if (x,z) in C: vox.append((x,y,z))
    PA={(x,y) for x,y,z in vox}; PB={(z,y) for x,y,z in vox}; PC={(x,z) for x,y,z in vox}
    return vox,PA,PB,PC

def vh_metrics(name,A,B,C):
    vox,PA,PB,PC=visual_hull(A,B,C)
    return dict(case=name, voxels=len(vox), front_iou=iou(A,PA), side_iou=iou(B,PB), top_iou=iou(C,PC), missing_front=len(A-PA), missing_side=len(B-PB), missing_top=len(C-PC), extra_front=len(PA-A), extra_side=len(PB-B), extra_top=len(PC-C))

# Compatible-ish top as Cartesian support from front/side rows, plus sparse cutout.
C_compatible=set()
for y in range(H):
    xs=[x for x in range(W) if (x,y) in front]
    zs=[z for z in range(D) if (z,y) in side]
    for x in xs:
        for z in zs:
            if (x-32)**2/30**2 + (z-32)**2/24**2 <= 1:
                C_compatible.add((x,z))
# Over-constrained top: diagonal ring unrelated to per-y supports.
C_bad=set()
for x in range(W):
    for z in range(D):
        if abs((x-z)-4) <= 2 or abs((x+z)-66) <= 2:
            if 10<x<54 and 8<z<56: C_bad.add((x,z))
# Soft top by dilating incompatible C to simulate slack.
def dilate_xz(C,r):
    out=set()
    for x,z in C:
        for dx in range(-r,r+1):
            for dz in range(-r,r+1):
                if dx*dx+dz*dz<=r*r and 0<=x+dx<W and 0<=z+dz<D: out.add((x+dx,z+dz))
    return out
vh_results=[vh_metrics('compatible_top_cutout',front,side,C_compatible), vh_metrics('overconstrained_diagonal_top',front,side,C_bad)]
for r in [1,2,4,8]:
    vh_results.append(vh_metrics(f'overconstrained_top_with_slack_dilate_r{r}', front, side, dilate_xz(C_bad,r)))

# Directional color basis toy: fit two endpoint colors using Lambert-like lobes, inspect mid-angle drift.
def color_lobe_error():
    # two orthogonal canonical views: front normal nf=(0,0,1), right nr=(1,0,0).
    cf=(1.0,0.55,0.15); cr=(0.1,0.55,1.0)
    rows=[]
    for deg in [0,15,30,45,60,75,90]:
        th=math.radians(deg)
        vf=max(0, math.cos(th))**8
        vr=max(0, math.sin(th))**8
        denom=max(1e-6,vf+vr)
        c=tuple((vf*cf[i]+vr*cr[i])/denom for i in range(3))
        # target interpolation is only a QA placeholder; physical color field should be smooth, not opacity-gated.
        t=deg/90
        target=tuple((1-t)*cf[i]+t*cr[i] for i in range(3))
        err=math.sqrt(sum((c[i]-target[i])**2 for i in range(3))/3)
        rows.append(dict(deg=deg, front_weight=round(vf/denom,3), right_weight=round(vr/denom,3), rmse=round(err,4)))
    return rows

print(json.dumps(dict(row_policy=row_results, visual_hull=vh_results, directional_color_lobe=color_lobe_error()), indent=2))
