"""Emit the GEMSDOE65 candidate raster from the SAR-propensity lane.

The surface is produced by the *same* code path that was scored on the blocked
folds (``scripts/run_lane.py``): SAR-EM selection model, propensity-weighted PU
risk with inverse weights clipped at 10, unit-mass dots allocated by the shared
``gems57.emit.greedy_allocate`` exact marginal test, with
``k_truth = pi * n_allowed``.  The only difference is the training set: for a
final artifact the whole published catalogue is legitimately visible.

Two encodings of the identical dot set are written:

* ``-zeros`` : all-finite raster, 0 outside the footprint.  This is the shared
  template's submission-compatible policy (``gems57.grid.write_submission``
  mode="zeros") and the variant recommended for upload.
* ``-nan``   : NaN outside the footprint, i.e. the sample_submission null mask.
  Diagnostics only (the organizer's nodata handling is not established, and a
  prior portal range error is not proven to have been caused by NaN).

``--allow-slot`` must be passed explicitly to mark the receipt as approved for a
weekly slot; it is refused unless the gate file says the lane passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems57 import gates  # noqa: E402
from gems57 import grid as G  # noqa: E402
from gems57 import metric  # noqa: E402
from gems57 import uniqueness  # noqa: E402
from gems57 import validate as V  # noqa: E402
from sar_pu import (CLIP, emit_cell, fit_head, fit_sar_em, fit_sar_em_rbf, phi,  # noqa: E402
                    predict_surface, standardizer)

from run_lane import STACK, UNL_CAP, _x_at  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--note", required=True)
    ap.add_argument("--outdir", default=str(ROOT / "docs" / "downloads"))
    ap.add_argument("--gate", default=str(ROOT / "registry" / "holdout_arms.json"))
    ap.add_argument("--allow-slot", action="store_true",
                    help="mark the receipt approved for a weekly slot (requires a passing gate)")
    ap.add_argument("--steps", type=int, default=1200)
    ap.add_argument("--propensity", choices=("rbf", "grid"), default="rbf",
                    help="selection model: rbf = continuous soft-binned SAR-EM (E3, corrected "
                         "pixel-population scale); grid = the earlier discretised model (E1/E2)")
    args = ap.parse_args()
    if len(args.note) > 140:
        raise SystemExit("note must be <= 140 characters")

    gate = json.loads(Path(args.gate).read_text())
    gate_pass = gate.get("gate", {}).get("verdict") == "promote"
    if args.allow_slot and not gate_pass:
        raise SystemExit("refusing --allow-slot: the registered gate verdict is not 'promote'")

    t0 = time.time()
    meta = json.loads((ROOT / "data" / "derived" / "feature_meta.json").read_text())
    stack = np.load(STACK, mmap_mode="r")
    grid = G.load_grid(ROOT / "data" / "bridge")
    fp, cat = grid.footprint, grid.catalogue
    pi = float(cat.sum()) / float(fp.sum())

    pos_r, pos_c = np.nonzero(cat)
    unl = fp & ~cat
    ur, uc = np.nonzero(unl)
    rng = np.random.default_rng(7)
    sel = rng.choice(ur.size, min(UNL_CAP, ur.size), replace=False)
    ur, uc = ur[sel], uc[sel]
    Xp, Xu = _x_at(stack, pos_r, pos_c), _x_at(stack, ur, uc)
    w_unl = np.full(Xu.shape[0], ur.size and int(unl.sum()) / max(Xu.shape[0], 1))
    cov = [meta["propensity_covariates"][k] for k in
           ("relief_1km", "slope", "basin_fill_gdd", "lidar_coverage", "dist_range_front_px")]
    # pixel-population scale: the unlabeled pool is subsampled, the catalogue is complete.
    # Without this ratio the EM fixed point collapses to e -> 1 (IR-65-106 / IR-65-111).
    pool_ratio = float(unl.sum()) / max(Xu.shape[0], 1)
    if args.propensity == "rbf":
        sar = fit_sar_em_rbf(Xp, Xu, cov, pi=pi, pool_ratio=pool_ratio, labelled_ratio=1.0,
                             labelled_complete=True, n_centers=32, seed=7)
    else:
        sar = fit_sar_em(Xp, Xu, cov, pi=pi, pool_ratio=pool_ratio, labelled_ratio=1.0,
                         labelled_complete=True)
    e_pos = sar.predict(Xp)
    w_pos = np.clip(1.0 / np.clip(e_pos, 1e-6, 1.0), 1.0, CLIP)
    mean, std = standardizer(np.vstack([Xp, Xu]))
    feat = lambda X: phi(X, mean, std)  # noqa: E731
    theta, fit = fit_head(Xp, w_pos, Xu, w_unl, feat, pi, "sar", steps=args.steps, lr=0.05, seed=20261011)

    allowed = fp & ~cat
    p = np.zeros(grid.shape, np.float32)
    ay, ax = np.nonzero(allowed)
    for i in range(0, ay.size, 400_000):
        rr, cc = ay[i:i + 400_000], ax[i:i + 400_000]
        p[rr, cc] = predict_surface(theta, _x_at(stack, rr, cc), mean, std)
    dots = emit_cell(p, allowed, pi)
    dots &= allowed
    n_dots = int(dots.sum())

    # how far the dots sit from the published catalogue (read-out for reviewers)
    try:
        from scipy.ndimage import distance_transform_edt
        dist_px = distance_transform_edt(~cat)
        dots_dist = dist_px[dots]
        dot_stats = dict(
            median_px=float(np.median(dots_dist)), p90_px=float(np.quantile(dots_dist, 0.9)),
            max_px=float(dots_dist.max()),
            fraction_within_3px=float((dots_dist <= 3).mean()),
            fraction_beyond_30px=float((dots_dist > 30).mean()))
    except Exception as exc:  # pragma: no cover - scipy is expected to be present
        dot_stats = dict(error=str(exc))

    values = np.zeros(grid.shape, np.float32)
    values[dots] = 1.0
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = args.name
    zeros_path = outdir / f"{stem}-zeros.tif"
    nan_path = outdir / f"{stem}-nan.tif"
    G.write_submission(zeros_path, values, mode="zeros")
    G.write_submission(nan_path, np.where(fp, values, np.nan).astype(np.float32), mode="nan")

    report = gates.format_report(zeros_path, ROOT / "data" / "bridge" / "sample_submission.tif", footprint=fp)
    local = V.validate(zeros_path, fp, cat)
    nan_local = V.validate(nan_path, fp, cat)
    receipt = dict(
        candidate=stem, generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        submission_name=args.name, note=args.note, note_chars=len(args.note),
        method=dict(lane="selection-bias-aware PU (SAR)",
                    propensity=("continuous RBF SAR-EM (soft-binned)" if args.propensity == "rbf"
                                else "discretised quantile-grid SAR-EM") + " on 5 covariates",
                    propensity_pool_ratio=pool_ratio,
                    propensity_scale_note="labelled sample is complete; unlabeled pool is subsampled, "
                                          "so the EM is run on pixel-population counts",
                    weights=f"inverse propensity clipped at {CLIP:g}", pi=pi,
                    emission="shared greedy_allocate exact marginal test",
                    fit=fit, propensity_model=sar.to_json(),
                    propensity_weight_stats=dict(
                        mean=float(w_pos.mean()), max=float(w_pos.max()),
                        fraction_clipped=float((e_pos >= CLIP - 1e-9).mean()),
                        e_pos_mean=float(e_pos.mean()), e_pos_min=float(e_pos.min()),
                        e_pos_max=float(e_pos.max()), e_pos_sd=float(e_pos.std()))),
        files={zeros_path.name: dict(sha256=report["sha256"], bytes=report["bytes"],
                                    validator=local["checks"], all_checks_passed=local["all_checks_passed"]),
               nan_path.name: dict(sha256=V.sha256(nan_path), validator=nan_local["checks"],
                                   all_checks_passed=nan_local["all_checks_passed"])},
        emitted_positive_pixels=n_dots,
        emitted_dot_distance_to_catalogue=dot_stats,
        gate=dict(verdict=gate.get("gate", {}).get("verdict"), source=str(args.gate),
                  approved_for_weekly_slot=bool(args.allow_slot and gate_pass)),
        runtime_seconds=round(time.time() - t0, 1),
        evidence_class="LOCAL-CANDIDATE (not a score; not organizer acceptance)",
    )
    (outdir / f"{stem}-receipt.json").write_text(json.dumps(receipt, indent=2, default=float) + "\n")
    print(json.dumps({k: receipt[k] for k in ("emitted_positive_pixels", "gate", "runtime_seconds")}, indent=2))
    print("format_report problems:", report["problems"])
    print("zeros validator all_pass:", local["all_checks_passed"], "| nan validator all_pass:", nan_local["all_checks_passed"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
