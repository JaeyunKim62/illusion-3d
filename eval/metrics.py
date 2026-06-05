"""Shared evaluation metrics for SDF visual-hull reconstruction."""

import json
import os

import numpy as np
import torch
from scipy.ndimage import distance_transform_edt


METRIC_REFERENCES = {
    "silhouetteMetrics": "IoU/precision/recall are standard binary mask overlap metrics used here as 2D supervision consistency.",
    "sdfConstraint": "SDF validity follows the visual-hull condition max(f_front, f_side, f_top) <= 0.",
    "boundaryDistance": "Boundary diagnostics use Euclidean distance transforms over binary masks.",
    "siren": "Sitzmann et al., Implicit Neural Representations with Periodic Activation Functions, NeurIPS 2020.",
    "standard3DWhenGroundTruthExists": "With 3D ground truth, add Chamfer Distance, F-score, Normal Consistency, and volumetric IoU.",
}


def open_training_metrics_log(
    path: str | None,
    *,
    n_iters: int,
    batch_size: int,
    lr: float,
    hidden: int,
    n_layers: int,
    eikonal_weight: float,
    metrics_interval: int,
    metrics_samples: int,
):
    if not path or metrics_interval <= 0:
        return None
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fp = open(path, "w")
    fp.write(json.dumps({
        "schema": "sdf-training-metrics/v1",
        "event": "config",
        "metricPolicy": {
            "stepLosses": "Logged every metrics interval from the training batches.",
            "sdfOutsideRatio": "Estimated by sampling candidate 3D points, accepting model-inside points, then checking them against exact EDT SDF constraints.",
            "projection": "Approximate projection IoU/recall/precision from the accepted monitor samples.",
        },
        "references": {
            key: METRIC_REFERENCES[key]
            for key in ("siren", "sdfConstraint", "silhouetteMetrics")
        },
        "config": {
            "iters": n_iters,
            "batchSize": batch_size,
            "lr": lr,
            "hidden": hidden,
            "layers": n_layers,
            "eikonalWeight": eikonal_weight,
            "metricsInterval": metrics_interval,
            "metricsSamples": metrics_samples,
        },
    }) + "\n")
    fp.flush()
    return fp


def write_training_metrics_step(fp, *, step: int, elapsed_sec: float, lr: float, losses: dict, monitor: dict):
    fp.write(json.dumps({
        "event": "trainStep",
        "step": step,
        "elapsedSec": elapsed_sec,
        "lr": lr,
        "losses": losses,
        "monitor": monitor,
    }) + "\n")
    fp.flush()


def normalized_to_pixels(points: np.ndarray, size: int):
    x = points[:, 0]
    y = points[:, 1]
    z = points[:, 2]
    col_x = np.clip(np.rint((x + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_y = np.clip(np.rint((1 - (y + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    col_z = np.clip(np.rint((z + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_z = np.clip(np.rint((1 - (z + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    return col_x, row_y, col_z, row_z


def projection_counts(points: np.ndarray, size: int):
    counts = {name: np.zeros((size, size), dtype=np.int32) for name in ("front", "side", "top")}
    if points.size:
        col_x, row_y, col_z, row_z = normalized_to_pixels(points, size)
        np.add.at(counts["front"], (row_y, col_x), 1)
        np.add.at(counts["side"], (row_y, col_z), 1)
        np.add.at(counts["top"], (row_z, col_x), 1)
    return counts


def density_stats(counts: np.ndarray, target: np.ndarray):
    target_counts = counts[target.astype(bool)]
    if target_counts.size == 0:
        return {
            "mean": 0.0,
            "median": 0.0,
            "p10": 0.0,
            "p90": 0.0,
            "max": 0,
            "emptyTargetRatio": 1.0,
            "overdrawRatio": 0.0,
        }
    active_counts = target_counts[target_counts > 0]
    return {
        "mean": float(target_counts.mean()),
        "median": float(np.median(target_counts)),
        "p10": float(np.percentile(target_counts, 10)),
        "p90": float(np.percentile(target_counts, 90)),
        "max": int(target_counts.max()),
        "emptyTargetRatio": float((target_counts == 0).sum() / target_counts.size),
        "overdrawRatio": float((active_counts.sum() - active_counts.size) / max(1, active_counts.sum())),
    }


def distance_stats(values: np.ndarray):
    if values.size == 0:
        return {"meanPx": 0.0, "medianPx": 0.0, "p95Px": 0.0, "maxPx": 0.0}
    return {
        "meanPx": float(values.mean()),
        "medianPx": float(np.median(values)),
        "p95Px": float(np.percentile(values, 95)),
        "maxPx": float(values.max()),
    }


def boundary_diagnostics(projected: np.ndarray, target: np.ndarray):
    projected = projected.astype(bool)
    target = target.astype(bool)
    missing = target & ~projected
    leakage = projected & ~target

    if projected.any():
        missing_dist = distance_transform_edt(~projected)[missing]
    else:
        missing_dist = np.asarray([], dtype=np.float32)

    if target.any():
        leakage_dist = distance_transform_edt(~target)[leakage]
    else:
        leakage_dist = np.asarray([], dtype=np.float32)

    return {
        "missingDistance": distance_stats(missing_dist),
        "leakageDistance": distance_stats(leakage_dist),
    }


def projection_metric(projected: np.ndarray, target: np.ndarray, counts: np.ndarray | None = None):
    projected = projected.astype(bool)
    target = target.astype(bool)
    intersection = projected & target
    union = projected | target
    leakage = projected & ~target
    missing = target & ~projected
    projected_active = int(projected.sum())
    target_active = int(target.sum())
    intersection_active = int(intersection.sum())
    leakage_active = int(leakage.sum())
    missing_active = int(missing.sum())
    out = {
        "targetActive": target_active,
        "projectedActive": projected_active,
        "intersection": intersection_active,
        "missing": missing_active,
        "leakage": leakage_active,
        "recall": intersection_active / max(1, target_active),
        "precision": intersection_active / max(1, projected_active),
        "iou": int(union.sum()) and intersection_active / int(union.sum()) or 0.0,
        "leakageRatio": leakage_active / max(1, projected_active),
        "missingRatio": missing_active / max(1, target_active),
    }
    if counts is not None:
        out["density"] = density_stats(counts, target)
    out["boundary"] = boundary_diagnostics(projected, target)
    return out


def projection_metrics_for_points(points: np.ndarray, masks: dict[str, np.ndarray], size: int, include_diagnostics: bool = True):
    counts = projection_counts(points, size)
    metrics = {}
    for name in ("front", "side", "top"):
        counts_arg = counts[name] if include_diagnostics else None
        metrics[name] = projection_metric(counts[name] > 0, masks[name], counts_arg)
    return metrics


def projection_summary(metrics: dict[str, dict]):
    return {
        "minRecall": min(v["recall"] for v in metrics.values()),
        "minPrecision": min(v["precision"] for v in metrics.values()),
        "maxLeakageRatio": max(v["leakageRatio"] for v in metrics.values()),
        "meanIoU": sum(v["iou"] for v in metrics.values()) / 3.0,
    }


def active_constraint_distribution(values):
    arr = np.asarray(values, dtype=np.int32)
    total = max(1, arr.size)
    labels = ["front", "side", "top"]
    return {
        labels[i]: {"count": int((arr == i).sum()), "ratio": float((arr == i).sum() / total)}
        for i in range(3)
    }


def projection_report(points: np.ndarray, masks: dict[str, np.ndarray], point_source: str, sdf_data: dict | None = None, size: int | None = None):
    if size is None:
        size = next(iter(masks.values())).shape[0]
    metrics = projection_metrics_for_points(points, masks, size, include_diagnostics=True)
    sdf_data = sdf_data or {}
    sdf_max = np.asarray(sdf_data.get("sdfMax", []), dtype=np.float32)
    positive = sdf_max > 1e-5 if sdf_max.size else np.asarray([], dtype=bool)
    report = {
        "schema": "sdf-projection-metrics/v2",
        "references": {
            key: METRIC_REFERENCES[key]
            for key in (
                "silhouetteMetrics",
                "sdfConstraint",
                "boundaryDistance",
                "standard3DWhenGroundTruthExists",
            )
        },
        "pointCloud": {"points": int(points.shape[0]), "source": point_source},
        "projectionDefinition": {"front": "(x,y)", "side": "(z,y)", "top": "(x,z)"},
        "metrics": metrics,
        "sdfValidity": {
            "hasSdfMax": bool(sdf_max.size),
            "positiveSdfCount": int(positive.sum()) if sdf_max.size else None,
            "positiveSdfRatio": float(positive.sum() / max(1, sdf_max.size)) if sdf_max.size else None,
            "maxPositiveSdf": float(sdf_max.max()) if sdf_max.size else None,
            "meanSdfMax": float(sdf_max.mean()) if sdf_max.size else None,
        },
        "activeConstraintDistribution": active_constraint_distribution(sdf_data.get("sdfActiveConstraint", [])),
    }
    report["summary"] = projection_summary(metrics)
    return report


def compute_bbox(masks: list[np.ndarray], pad: float = 0.05):
    mask_f, mask_s, mask_t = masks
    size = mask_f.shape[0]

    def axis_range(mask, axis):
        proj = mask.any(axis=axis)
        idx = np.where(proj)[0]
        if len(idx) == 0:
            return -1.0, 1.0
        lo = idx[0] / (size - 1) * 2 - 1
        hi = idx[-1] / (size - 1) * 2 - 1
        return lo - pad, hi + pad

    x_lo, x_hi = axis_range(mask_f, 0)
    y_lo_f, y_hi_f = axis_range(mask_f, 1)
    y_lo_f, y_hi_f = -y_hi_f, -y_lo_f

    z_lo, z_hi = axis_range(mask_s, 0)
    y_lo_s, y_hi_s = axis_range(mask_s, 1)
    y_lo_s, y_hi_s = -y_hi_s, -y_lo_s

    x_lo2, x_hi2 = axis_range(mask_t, 0)
    z_lo2, z_hi2 = axis_range(mask_t, 1)
    z_lo2, z_hi2 = -z_hi2, -z_lo2

    lo = np.array([max(x_lo, x_lo2), max(y_lo_f, y_lo_s), max(z_lo, z_lo2)], dtype=np.float32).clip(-1, 1)
    hi = np.array([min(x_hi, x_hi2), min(y_hi_f, y_hi_s), min(z_hi, z_hi2)], dtype=np.float32).clip(-1, 1)
    return lo, hi


def eval_sdf_batched(models: dict[str, torch.nn.Module], xyz: torch.Tensor, batch: int = 50_000):
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    d_parts = []
    for i in range(0, len(x), batch):
        sl = slice(i, i + batch)
        fa = models["front"](torch.stack([x[sl], y[sl]], dim=1))
        fb = models["side"](torch.stack([z[sl], y[sl]], dim=1))
        fc = models["top"](torch.stack([x[sl], z[sl]], dim=1))
        d_parts.append(torch.maximum(torch.maximum(fa, fb), fc))
    return torch.cat(d_parts)


def true_sdf_values_for_points(points: np.ndarray, sdf_arrays: dict[str, np.ndarray], size: int):
    if points.size == 0:
        return np.asarray([], dtype=np.float32)
    col_x, row_y, col_z, row_z = normalized_to_pixels(points, size)
    front = sdf_arrays["front"][row_y, col_x]
    side = sdf_arrays["side"][row_y, col_z]
    top = sdf_arrays["top"][row_z, col_x]
    return np.maximum.reduce([front, side, top]).astype(np.float32)


@torch.no_grad()
def training_monitor_snapshot(
    models: dict[str, torch.nn.Module],
    masks: dict[str, np.ndarray],
    sdf_arrays: dict[str, np.ndarray],
    device: torch.device,
    sample_count: int,
):
    size = next(iter(masks.values())).shape[0]
    lo, hi = compute_bbox([masks["front"], masks["side"], masks["top"]])
    lo_t = torch.tensor(lo, dtype=torch.float32, device=device)
    hi_t = torch.tensor(hi, dtype=torch.float32, device=device)
    xyz = torch.rand(sample_count, 3, device=device) * (hi_t - lo_t) + lo_t
    pred_sdf = eval_sdf_batched(models, xyz)
    inside = pred_sdf <= 0
    points = xyz[inside].detach().cpu().numpy().astype(np.float32)
    true_sdf_max = true_sdf_values_for_points(points, sdf_arrays, size)
    positive = true_sdf_max > 1e-5 if true_sdf_max.size else np.asarray([], dtype=bool)
    projection = projection_metrics_for_points(points, masks, size, include_diagnostics=False)
    summary = projection_summary(projection)
    return {
        "candidateSamples": int(sample_count),
        "acceptedSamples": int(points.shape[0]),
        "predictedInsideRatio": float(inside.float().mean().detach().cpu()),
        "sdfOutsideRatio": float(positive.sum() / max(1, true_sdf_max.size)),
        "maxPositiveSdf": float(true_sdf_max.max()) if true_sdf_max.size else None,
        "meanSdfMax": float(true_sdf_max.mean()) if true_sdf_max.size else None,
        "projection": projection,
        "summary": summary,
    }
