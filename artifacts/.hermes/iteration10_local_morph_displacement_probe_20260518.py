from pathlib import Path
from PIL import Image
import numpy as np
import json

try:
    from scipy.ndimage import distance_transform_edt, label
except Exception as e:
    distance_transform_edt = None
    label = None

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'algorithm-exploration' / 'iteration-10-local-morph-displacement-probe-20260518.json'
REF = ROOT / 'artifacts' / 'reference-image'

W, H = 160, 120


def load_mask(name):
    im = Image.open(REF / name).convert('RGBA')
    im.thumbnail((W, H), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (W, H), (255, 255, 255, 0))
    canvas.alpha_composite(im, ((W - im.width)//2, (H - im.height)//2))
    arr = np.array(canvas)
    alpha = arr[..., 3]
    rgb = arr[..., :3]
    # Reference assets are alpha images; keep fallback for non-alpha/non-white.
    mask = (alpha >= 64) | ((rgb.mean(axis=2) < 245) & (alpha > 0))
    return mask.astype(bool)


def shift_mask(mask, dx=0, dy=0):
    out = np.zeros_like(mask)
    ys, xs = np.where(mask)
    nx = xs + dx
    ny = ys + dy
    ok = (nx >= 0) & (nx < mask.shape[1]) & (ny >= 0) & (ny < mask.shape[0])
    out[ny[ok], nx[ok]] = True
    return out


def right_tail_region(mask, q=0.75):
    ys, xs = np.where(mask)
    cutoff = int(np.quantile(xs, q))
    region = mask.copy()
    region[:, :cutoff] = False
    return region, cutoff


def local_shift_target(mask, region, dx=0, dy=0):
    base_without = mask & (~region)
    moved = shift_mask(region, dx=dx, dy=dy)
    return base_without | moved


def comp_stats(mask):
    if label is None:
        return {}
    lab, n = label(mask)
    if n == 0:
        return {'component_count': 0, 'largest_component_ratio': 0.0}
    counts = np.bincount(lab.ravel())[1:]
    return {
        'component_count': int(n),
        'largest_component_ratio': float(counts.max() / max(1, mask.sum()))
    }


def compare_support(base, target, tolerances=(0,1,2,4,8,12)):
    create = target & (~base)
    erase = base & (~target)
    sym = create | erase
    result = {
        'base_pixels': int(base.sum()),
        'target_pixels': int(target.sum()),
        'intersection': int((base & target).sum()),
        'union': int((base | target).sum()),
        'iou': float((base & target).sum() / max(1, (base | target).sum())),
        'create_missing_pixels': int(create.sum()),
        'erase_needed_pixels': int(erase.sum()),
        'create_missing_ratio_vs_target': float(create.sum() / max(1, target.sum())),
        'erase_ratio_vs_base': float(erase.sum() / max(1, base.sum())),
        'symmetric_diff_ratio_vs_union': float(sym.sum() / max(1, (base | target).sum())),
        'color_only_pass_1pct': bool(create.sum() / max(1, target.sum()) <= 0.01 and erase.sum() / max(1, base.sum()) <= 0.01),
    }
    if distance_transform_edt is not None:
        # For each new target pixel, distance to nearest existing support; for each erased base pixel, distance to target support.
        dist_to_base = distance_transform_edt(~base)
        dist_to_target = distance_transform_edt(~target)
        create_dist = dist_to_base[create]
        erase_dist = dist_to_target[erase]
        all_dist = np.concatenate([create_dist, erase_dist]) if create_dist.size + erase_dist.size else np.array([0.0])
        result.update({
            'create_distance_p50': float(np.percentile(create_dist, 50)) if create_dist.size else 0.0,
            'create_distance_p95': float(np.percentile(create_dist, 95)) if create_dist.size else 0.0,
            'erase_distance_p50': float(np.percentile(erase_dist, 50)) if erase_dist.size else 0.0,
            'erase_distance_p95': float(np.percentile(erase_dist, 95)) if erase_dist.size else 0.0,
            'symdiff_distance_p95': float(np.percentile(all_dist, 95)) if all_dist.size else 0.0,
        })
        tol_stats = {}
        for eps in tolerances:
            new_covered = float((create_dist <= eps).sum() / max(1, create_dist.size)) if create_dist.size else 1.0
            erase_covered = float((erase_dist <= eps).sum() / max(1, erase_dist.size)) if erase_dist.size else 1.0
            tol_stats[str(eps)] = {
                'create_diff_within_eps_ratio': new_covered,
                'erase_diff_within_eps_ratio': erase_covered,
                'both_95pct_within_eps': bool(new_covered >= 0.95 and erase_covered >= 0.95),
            }
        result['tolerance_sweep'] = tol_stats
        # Classify: pure color cannot pass once create/erase > 1%; micro-displacement only if most diff is near old/new support and affected area is localized.
        if result['color_only_pass_1pct']:
            cls = 'color_only_feasible'
        elif result['symdiff_distance_p95'] <= 2 and result['symmetric_diff_ratio_vs_union'] <= 0.15:
            cls = 'micro_displacement_candidate_strong'
        elif result['symdiff_distance_p95'] <= 4 and result['symmetric_diff_ratio_vs_union'] <= 0.30:
            cls = 'micro_displacement_candidate_borderline'
        else:
            cls = 'geometry_needed_or_defer'
        result['morph_classification'] = cls
    result.update(comp_stats(target))
    return result


def main():
    masks = {name: load_mask(name) for name in ['goose.png', 'nubzuki.png', 'cake.png', 'phoenix.png', 'kumdori.png']}
    base = masks['goose.png']
    limb, cutoff = right_tail_region(base, 0.75)
    out = {
        'resolution': [W, H],
        'method': {
            'color_only_condition': 'create_missing_ratio_vs_target<=0.01 and erase_ratio_vs_base<=0.01',
            'micro_displacement_candidate_strong': 'symdiff_distance_p95<=2px and symmetric_diff_ratio_vs_union<=0.15',
            'micro_displacement_candidate_borderline': 'symdiff_distance_p95<=4px and symmetric_diff_ratio_vs_union<=0.30',
            'limb_region': 'rightmost 25% x-quantile of goose support, shifted while rest of support stays fixed',
        },
        'goose_base_pixels': int(base.sum()),
        'goose_right_tail_cutoff_x': int(cutoff),
        'goose_right_tail_pixels': int(limb.sum()),
        'whole_object_shift': {},
        'localized_right_tail_shift': {},
        'asset_support_mismatch_vs_goose': {},
    }
    for dx in [1,2,4,8,12]:
        out['whole_object_shift'][f'right_{dx}px'] = compare_support(base, shift_mask(base, dx=dx))
        out['localized_right_tail_shift'][f'right_tail_{dx}px'] = compare_support(base, local_shift_target(base, limb, dx=dx))
    for dy in [1,2,4,8]:
        out['whole_object_shift'][f'down_{dy}px'] = compare_support(base, shift_mask(base, dy=dy))
        out['localized_right_tail_shift'][f'right_tail_down_{dy}px'] = compare_support(base, local_shift_target(base, limb, dy=dy))
    for name, mask in masks.items():
        if name == 'goose.png':
            continue
        out['asset_support_mismatch_vs_goose'][name] = compare_support(base, mask)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(OUT)

if __name__ == '__main__':
    main()
