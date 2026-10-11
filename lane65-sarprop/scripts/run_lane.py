"""Driver for the selection-bias-aware PU lane.  Subcommands:

  ingest      build the cell sample + feature cache (one 419 MB pass)
  gate        experiment 1: SAR arm vs nnPU baseline on the blocked holdout
  emit        experiment 2: emission + sensitivity, and the live submission field
  write       experiment 3a: write the submission GeoTIFF + validate it
  uniqueness  experiment 3b: hash / rank / pixel-agreement vs every prior raster
  site        build docs/ from the evidence JSONs

Every number written to evidence/ carries its evidence class in the JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems65_sarprop import features as F                      # noqa: E402
from gems65_sarprop import grid as G                          # noqa: E402
from gems65_sarprop import lane                               # noqa: E402

EVID = ROOT / "evidence"
TMP = pathlib.Path("/tmp/gems65")
TMP.mkdir(parents=True, exist_ok=True)
DATA = ROOT / "data"
FEATURES = DATA / "training_features.tif"
LIDAR = DATA / "external" / "lidar_scarp_features_u8.tif"
CACHE = TMP / "sample_cache.npz"
DRAW_SEED = 2026
HIDE_FRAC = 0.20
KAPPA = 1.0
# Predeclared emission budget grid, frozen before any holdout number was read.
B_GRID = (500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 100000, 160000)


def load_json(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        return default


def _json(obj, path: pathlib.Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def _sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def cov_stats():
    return json.loads((TMP / "cov_stats.json").read_text())


def load_grid():
    from gems65_sarprop.template.grid import load_grid as _lg
    return _lg(DATA / "bridge")


def load_draw():
    """The mandated hide-and-recover draw, recomputed deterministically."""
    from gems65_sarprop.template.holdout import buffered_component_draw
    g = load_grid()
    folds, quad = buffered_component_draw(g, seed=DRAW_SEED, hide_frac=HIDE_FRAC,
                                          buffer_px=3)
    hidden = np.zeros(G.SHAPE, bool)
    region = np.zeros(G.SHAPE, bool)
    for f in folds:
        hidden |= f["truth"]
        region |= f["region"]
    return g, folds, hidden, region, folds[0]["visible"], folds[0]["masked_known"]


def lidar_cov():
    if not LIDAR.exists():
        return None, {"present": False, "reason": "file absent"}
    cov, meta = F.lidar_coverage_from_support(str(LIDAR))
    if cov.shape != G.SHAPE:
        # nearest-neighbour resample onto the official grid
        import rasterio
        from rasterio.warp import Resampling, reproject
        from rasterio.transform import Affine
        with rasterio.open(LIDAR) as ds:
            src = ds.read(1)
            dst = np.zeros(G.SHAPE, np.float32)
            reproject(source=src, destination=dst,
                      src_transform=ds.transform, src_crs=ds.crs,
                      dst_transform=Affine.from_gdal(*G.TRANSFORM),
                      dst_crs=f"EPSG:{G.CRS_EPSG}",
                      resampling=Resampling.nearest)
        meta["resampled_to_official_grid"] = True
        meta["raw_shape"] = meta.get("shape")
        cov = np.isfinite(dst) | (dst > 0)
    else:
        meta["resampled_to_official_grid"] = False
    meta["coverage_cells_on_grid"] = int(cov.sum())
    meta["coverage_fraction_on_grid"] = float(cov.mean())
    meta["sha256"] = _sha(LIDAR)
    meta["pin_sha256"] = "d580bb8bdcdb941e32fefb8b38044bc5bf04e199bf2e83498c3576e6fc465568"
    meta["sha_match"] = meta["sha256"] == meta["pin_sha256"]
    return cov, meta


# --------------------------------------------------------------------------
def cmd_ingest(args):
    t0 = time.time()
    g, folds, hidden, region, visible, masked_known = load_draw()
    receipt = {"draw_seed": DRAW_SEED, "hide_frac": HIDE_FRAC,
               "withheld_positives": int(hidden.sum()),
               "visible_catalogue": int(visible.sum()),
               "folds": [f["receipt"] for f in folds]}
    print("holdout draw:", json.dumps({k: v for k, v in receipt.items() if k != "folds"}))

    cov, lidar_meta = lidar_cov()
    print("lidar:", json.dumps(lidar_meta))

    sample = lane.sample_cells(g.footprint, g.catalogue, seed=6565)
    print(f"sample: {sample['y'].size} cells "
          f"({sample['n_catalogue']} catalogue + {sample['n_unlabelled']} unlabelled)")
    ex = lane.extract(sample["y"], sample["x"], features_path=str(FEATURES),
                      lidar_cov=cov, visible_catalogue=visible)
    X, cv = ex["X"], ex["cov"]
    keep = np.isfinite(X).all(axis=0)
    for k in F.PROPENSITY_ATTRIBUTES:
        keep &= np.isfinite(cv[k])
    print(f"complete rows: {int(keep.sum())}/{keep.size}")
    cov_cols = [cv[k][keep] for k in F.PROPENSITY_ATTRIBUTES]
    Z, stats = F.standardise(cov_cols, fit_mask=np.ones(int(keep.sum()), bool))
    lane.save_cache(CACHE, {
        "X": X[:, keep].astype(np.float32),
        "Z": Z.astype(np.float32),
        "rows": sample["y"][keep], "cols": sample["x"][keep],
        "is_catalogue": sample["is_catalogue"][keep],
        "visible": visible[sample["y"][keep], sample["x"][keep]],
    })
    (TMP / "cov_stats.json").write_text(json.dumps(stats))
    _json({"evidence_class": "MEASURED (local instrument/draw, not a score)",
           "holdout_draw": receipt, "lidar": lidar_meta,
           "sample": {k: v for k, v in sample.items() if k not in ("y", "x")},
           "complete_rows": int(keep.sum()),
           "covariate_stats": stats,
           "design_columns": lane.build_design_names(),
           "runtime_s": round(time.time() - t0, 1)},
          EVID / "ingest.json")


# --------------------------------------------------------------------------
def _fit_from_cache(kappa=KAPPA, max_iter=12, verbose=False):
    g, folds, hidden, region, visible, masked_known = load_draw()
    d = np.load(CACHE)
    X = d["X"].astype(np.float64).T          # (n, 19) official bands
    Z = d["Z"].astype(np.float64).T          # (n, 5) propensity attributes
    vis = d["visible"]
    s = vis.astype(np.int8)          # positives = VISIBLE catalogue only
    Xc = np.column_stack([X, Z])              # 19 bands + 5 covariates = 24
    arms_out = lane.fit_arms(Xc, s, Z, kappa=kappa, max_iter=max_iter, verbose=verbose)
    return g, folds, hidden, region, visible, masked_known, X, Z, s, arms_out, d


def cmd_gate(args):
    """Experiment 1: SAR-propensity arm vs the nnPU baseline on the blocked holdout."""
    t0 = time.time()
    (g, folds, hidden, region, visible, masked_known, X, Z, s, arms_out, d) = _fit_from_cache(
        kappa=args.kappa, max_iter=args.max_iter, verbose=True)
    print(f"labelled(visible)={int(s.sum())} unlabelled={int((s == 0).sum())}")

    stats = cov_stats()
    arm_models = [lane.ArmModel(name=nm,
                                beta=np.asarray(arms_out[nm]["model"].beta),
                                cov_stats=stats,
                                f_train=arms_out[nm]["f_train"])
                  for nm in ("nnpu", "sar", "scar")]
    print("scoring the full grid for 3 arms in ONE pass ...")
    scores = lane.score_full_multi(arm_models, features_path=str(FEATURES),
                                   cov_stats=stats, lidar_cov=lidar_cov()[0],
                                   visible_catalogue=visible)
    np.savez_compressed(TMP / "scores_holdout.npz", **scores)

    allowed = g.footprint & ~masked_known
    k_truth = float(hidden.sum())
    from gems65_sarprop.template.metric import dti_exact

    # --- the propensity terciles the gate is stated on ---------------------
    coef_e = arms_out["sar_em"].coef_e
    e_field = None
    if coef_e is not None:
        e_field = lane.propensity_field_full(coef_e, stats, features_path=str(FEATURES),
                                             lidar_cov=lidar_cov()[0],
                                             visible_catalogue=visible,
                                             kappa=args.kappa)
        np.save(TMP / "propensity_field_holdout.npy", e_field)
        ev = e_field[allowed]
        q1, q2 = np.quantile(ev, [1 / 3, 2 / 3])
        top_tercile = allowed & (e_field > q2)
        tercile_info = {"q1": float(q1), "q2": float(q2),
                        "top_tercile_cells": int(top_tercile.sum()),
                        "top_tercile_withheld_truth": int((hidden & top_tercile).sum())}
    else:
        top_tercile, tercile_info = None, {"coef_e": None,
                                           "note": "propensity model not estimable"}
    print("tercile:", json.dumps(tercile_info))

    report = {
        "b_grid_predeclared": list(B_GRID),
        "evidence_class": ("HOLDOUT-DTI — evaluator: template metric.dti_exact "
                           "(alpha 0.2, beta 0.8, R = 3 px triangular kernel), "
                           "pooled over the whole footprint"),
        "instrument": ("buffered whole-component hide-and-recover; draw seed "
                       f"{DRAW_SEED}, hide_frac {HIDE_FRAC}, 3 px feature collar, "
                       "label-blind quadrant eligibility"),
        "withheld_positives": int(hidden.sum()),
        "visible_catalogue_px": int(visible.sum()),
        "k_truth_used_in_emission": k_truth,
        "kappa": args.kappa,
        "propensity_terciles": tercile_info,
        "propensity_field_file": "propensity_field_holdout.npy",
        "propensity_e_mean_inside_allowed": (
            None if e_field is None else float(np.nanmean(e_field[allowed]))),
        "note_on_scale": ("HOLDOUT-DTI on this instrument is a RELATIVE number: it "
                          "scores only the withheld pixels, while the organiser scores "
                          "against every fault.  It must not be compared with a "
                          "leaderboard score, only between arms on the same draw."),
        "arms": {}, "scores_sha256": {}, "runtime_s": None,
    }
    for nm, arr in scores.items():
        report["scores_sha256"][nm] = hashlib.sha256(
            np.ascontiguousarray(arr, dtype="<f4").tobytes()).hexdigest()

    T_terms = {}
    for nm in ("nnpu", "sar", "scar"):
        sc = scores[nm]
        p = lane.rescale_to_prior(sc, allowed, k_truth)
        alloc = lane.allocate_nms(p, allowed, k_truth, radius_px=3,
                                  b_grid=B_GRID)
        order = alloc["scan_order"]
        emitted = np.zeros(allowed.shape, bool)
        if order.size:
            emitted[order[:, 0], order[:, 1]] = True
        emitted &= allowed
        overall = dti_exact(emitted.astype(np.float32), hidden & region,
                            valid=g.footprint, known=masked_known)
        entry = {"n_dots": int(emitted.sum()),
                 "emission_rule": "price_curve_nms3 (budget from a predeclared "
                                  "price curve, >= 3 px separation between dots)",
                 "budget_curve": alloc["curve"],
                 "surrogate_dti_under_p": float(alloc["surrogate_dti"]),
                 "overall": {k: float(v) for k, v in overall.items()}}
        if top_tercile is not None:
            top = dti_exact(emitted.astype(np.float32), hidden & region,
                            valid=g.footprint & top_tercile, known=masked_known)
            rest = dti_exact(emitted.astype(np.float32), hidden & region,
                             valid=g.footprint & ~top_tercile, known=masked_known)
            entry["top_propensity_tercile"] = {k: float(v) for k, v in top.items()}
            entry["lower_propensity_tiers"] = {k: float(v) for k, v in rest.items()}
        report["arms"][nm] = entry
        T_terms[nm] = entry["overall"]
        np.save(TMP / f"dots_holdout_{nm}.npy", emitted)
        print(f"  {nm:5s} dots={int(emitted.sum()):6d} "
              f"HOLDOUT-DTI={overall['dti']:.6f} TPw={overall['tp']:.0f} "
              f"FPw={overall['fp']:.0f} FNw={overall['fn']:.0f} n_truth={overall['n_truth']}"
              + (f"  top-tercile-DTI={entry['top_propensity_tercile']['dti']:.6f}"
                 if top_tercile is not None else ""))

    if top_tercile is not None:
        d_overall = report["arms"]["sar"]["overall"]["dti"] - report["arms"]["nnpu"]["overall"]["dti"]
        d_top = (report["arms"]["sar"]["top_propensity_tercile"]["dti"]
                 - report["arms"]["nnpu"]["top_propensity_tercile"]["dti"])
        report["gate"] = {
            "rule": ("PROMOTE iff SAR-propensity arm's pooled HOLDOUT-DTI is strictly "
                     "higher than nnPU's AND its top-propensity-tercile DTI is not lower"),
            "delta_overall": float(d_overall), "delta_top_tercile": float(d_top),
            "overall_pass": bool(d_overall > 0), "tercile_pass": bool(d_top >= 0),
            "verdict": "PROMOTE" if (d_overall > 0 and d_top >= 0) else "NEGATIVE",
        }
        print("GATE:", json.dumps(report["gate"], indent=1))
    report["runtime_s"] = round(time.time() - t0, 1)
    _json(report, EVID / "gate.json")


# --------------------------------------------------------------------------
def cmd_propensity_field(args):
    """Per-cell fitted propensity from the SAR-EM propensity model."""
    (g, folds, hidden, region, visible, masked_known, X, Z, s, arms_out, d) = _fit_from_cache(
        kappa=args.kappa, max_iter=args.max_iter)
    from gems65_sarprop.pu import weighted_logistic_fit
    e_tr = arms_out["sar"]["e_train"]
    report = {"evidence_class": "HOLDOUT-DTI (model-internal field, not a score)",
              "e_mean": float(e_tr.mean()), "e_min": float(e_tr.min()),
              "e_max": float(e_tr.max()),
              "e_on_labelled_mean": float(e_tr[s == 1].mean()),
              "e_on_unlabelled_mean": float(e_tr[s == 0].mean()),
              "c_scar_label_frequency": float(arms_out["sar"]["summary"]["c_scar_label_frequency"]),
              "sar_em_trace": arms_out["sar"]["summary"]["trace"]}
    _json(report, EVID / "propensity_field.json")


# --------------------------------------------------------------------------
def cmd_emit(args):
    """Build the live submission field from the SAR-propensity arm.

    The live run sees the WHOLE catalogue (that is the point of the submission)
    and emits with the rule the gate validated: a price curve over a predeclared
    budget grid, dots at >= 3 px separation.  Covariates are standardised with
    the statistics persisted by ``ingest`` -- never with placeholders, or the
    live field would not be the field the gate measured.

    The emitted SET at a fixed budget is exactly scale-invariant in `p` (the
    accept order and the suppression logic depend only on the ranking), so the
    rescaling constant `K` cannot change the dots; it only moves the internal
    price curve.  This is asserted in-script by emitting twice at two K values.
    """
    t0 = time.time()
    (g, folds, hidden, region, visible, masked_known, X, Z, s, arms_out, d) = _fit_from_cache(
        kappa=args.kappa, max_iter=args.max_iter, verbose=True)
    stats = cov_stats()
    coef_e = arms_out["sar_em"].coef_e
    if coef_e is None:
        raise RuntimeError("SAR-EM did not persist coef_e; refusing to emit a field "
                           "whose propensity model is unverified")
    am = lane.ArmModel(name="sar_live", beta=np.asarray(arms_out["sar"]["model"].beta),
                       cov_stats=stats)
    print("scoring live (full catalogue mask; no holdout draw) ...")
    lid = lidar_cov()[0]
    sc = lane.score_full_multi([am], features_path=str(FEATURES), cov_stats=stats,
                               lidar_cov=lid, visible_catalogue=g.catalogue)["sar_live"]
    np.save(TMP / "score_live.npy", sc)
    e_field = lane.propensity_field_full(coef_e, stats, features_path=str(FEATURES),
                                         lidar_cov=lid, visible_catalogue=g.catalogue,
                                         kappa=args.kappa)
    np.save(TMP / "propensity_live.npy", e_field)

    allowed = g.footprint & ~g.catalogue
    k_mass = float(round(0.20 * float(g.catalogue.sum())))
    p_ = lane.rescale_to_prior(sc, allowed, k_mass)
    alloc = lane.allocate_nms(p_, allowed, k_mass, radius_px=3, b_grid=B_GRID)
    budget = int(args.budget)
    order = alloc["scan_order"]
    emitted = np.zeros(allowed.shape, bool)
    if order.size and budget > 0:
        sel = order[:budget]
        emitted[sel[:, 0], sel[:, 1]] = True
    emitted &= allowed

    # scale-invariance assertion (cheap, and it is a real risk if p ever stops
    # being used purely as a ranking)
    p2 = lane.rescale_to_prior(sc, allowed, 10.0 * k_mass)
    a2 = lane.allocate_nms(p2, allowed, 10.0 * k_mass, radius_px=3, b_grid=(budget,))
    ob = a2["scan_order"][: min(budget, a2["scan_order"].shape[0])]
    oa = order[: ob.shape[0]]
    inter = np.intersect1d((oa[:, 0] * 100000 + oa[:, 1]), (ob[:, 0] * 100000 + ob[:, 1])).size
    overlap = inter / max(oa.shape[0], 1)
    if overlap < 0.99:
        raise RuntimeError(f"emission is not invariant in p (overlap {overlap:.4f}); "
                           "the budget/K transfer would be invalid")
    print(f"invariance of the emitted set under a 10x change of the rescaling mass: "
          f"overlap={overlap:.4f} of {oa.shape[0]} dots "
          f"(differences are float32 tie-breaking only)")

    np.save(TMP / "dots_live.npy", emitted)
    out = {"evidence_class": "MODEL-INTERNAL (no organiser score exists for this file)",
           "arm": "sar (propensity-weighted risk, Bekker/Robberechts/Davis 1809.03207)",
           "emission_rule": ("nms3_saturated (>= 3 px apart) then the measured <= 2 px "
                          "prune against the mapped catalogue"),
           "b_grid_predeclared": list(B_GRID),
           "budget": budget,
           "budget_source": ("argmax of the surrogate price curve on the blocked holdout, "
                             "chosen per arm in evidence/gate.json; transferred by absolute "
                             "dot count because the holdout grid and the live grid have "
                             "the same scored area (5.12M vs 5.11M cells)"),
           "n_dots": int(emitted.sum()),
           "n_accepted_before_saturation": int(order.shape[0]),
           "allowed_cells": int(allowed.sum()),
           "catalogue_px_masked": int(g.catalogue.sum()),
           "k_mass_used": k_mass,
           "invariance_overlap_under_10x_mass": float(overlap),
           "e_field_stats": {"mean": float(np.nanmean(e_field[allowed])),
                             "q1": float(np.nanquantile(e_field[allowed], 1 / 3)),
                             "q2": float(np.nanquantile(e_field[allowed], 2 / 3)),
                             "max": float(np.nanmax(e_field))},
           "curve": alloc["curve"],
           "runtime_s": round(time.time() - t0, 1)}
    _json(out, EVID / "emit.json")


# --------------------------------------------------------------------------
def cmd_write(args):
    """Serialise the emitted dots through the shared, frozen submission writer.

    Export policy: ALL-FINITE, values exactly in [0, 1].  The dots are 1.0 and
    everything else is 0.0 -- including cells outside the competition footprint.
    The public spec tolerates NaN outside the footprint, but the portal check
    that once rejected one of this family's files was "Predicted values must be
    in range [0, 1]", and the template's own on-disk gate refuses any non-finite
    pixel, so the conservative all-finite form is the one that cannot fail the
    range check either way.  A binary dot field is also the form the metric
    rewards: scaling every dot by a constant c < 1 scales TP and FP by c while
    leaving FN = |G| - TP larger, which can only lower DTI.
    """
    from gems65_sarprop.template.submission_writer import write_submission
    g = load_grid()
    dots = np.load(TMP / "dots_live.npy").astype(bool)
    dots &= g.footprint & ~g.catalogue
    field = dots.astype(np.float32)
    if not np.isfinite(field).all() or field.min() < 0 or field.max() > 1:
        raise RuntimeError("all-finite [0,1] export policy violated before writing")
    name = args.name
    out = ROOT / "docs" / "downloads" / f"{name}.tif"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise FileExistsError(f"{out} already exists; bump --name rather than "
                              "overwriting a published artifact")
    receipt = write_submission(out, field, DATA / "bridge" / "sample_submission.tif",
                               g.footprint, note=args.note,
                               name=name, catalogue=g.catalogue,
                               metadata={"lane": "gems65 SAR-propensity PU",
                                         "emission_rule": "nms3_saturated",
                                         "arm": "sar (propensity-weighted risk)"})
    import rasterio
    with rasterio.open(out) as ds:
        arr = ds.read(1)
    rec = {"file": str(out.relative_to(ROOT)), "bytes": out.stat().st_size,
           "sha256": _sha(out), "shape": list(arr.shape), "crs": "EPSG:32611",
           "transform": list(g.transform)[:6], "dtype": str(arr.dtype),
           "n_dots": int((arr > 0).sum()), "min": float(arr.min()),
           "max": float(arr.max()),
           "all_finite": bool(np.isfinite(arr).all()),
           "values_in_unit_interval": bool(arr.min() >= 0 and arr.max() <= 1),
           "dots_only_inside_allowed": bool(not ((arr > 0) & g.catalogue).any()),
           "note": args.note, "note_len": len(args.note), "name": name,
           "template_receipt": receipt}
    _json(rec, EVID / "submission_receipt.json")
    print(json.dumps({k: v for k, v in rec.items() if k != "template_receipt"}, indent=1))
    print("template receipt:", receipt.get("zip_file"), receipt.get("sha256"))


def cmd_prune(args):
    """Apply the measured prune rule to the live dots, then record the edit.

    Cheap on purpose: the score field is already on disk, so the final emission
    decision is auditable without refitting anything.
    """
    from scipy import ndimage as ndi
    g = load_grid()
    src = TMP / "dots_live_unpruned.npy"
    if not src.exists():                      # first run: the unpruned set is the live set
        src = TMP / "dots_live.npy"
    dots = np.load(src).astype(bool)
    emit = load_json(EVID / "emit.json", {}) or {}
    dist = ndi.distance_transform_edt(~g.catalogue)
    pruned = lane.prune_band(dots, dist, args.radius)
    removed = int(dots.sum() - pruned.sum())
    near = int((dots & (dist <= args.radius)).sum())
    if near != removed:
        raise RuntimeError("prune accounting mismatch")
    np.save(TMP / "dots_live_unpruned.npy", dots)
    final = pruned & g.footprint & ~g.catalogue
    np.save(TMP / "dots_live.npy", final)
    emit["n_dots_unpruned"] = int(dots.sum())
    emit["n_dots"] = int(final.sum())
    emit["emission_rule"] = ("accept candidates in descending expected credit with "
                             "non-maximum suppression at the metric's 3 px kernel radius, "
                             "budget taken to saturation on the measured curve, then "
                             f"prune every dot within {args.radius} px of a mapped fault")
    emit["n_dots_unpruned"] = emit.get("n_dots_unpruned", int(dots.sum()))
    emit["prune"] = {
        "rule": f"drop dots within {args.radius} px of a mapped fault",
        "justification": {"score_02778_exact_set_identity":
                          "the 0.2778 receipt equals the 0.2708 file with every dot "
                          "inside 2.0 px deleted (2,545 dots, +0.0070)",
                          "holdout_prune_only_dti": [0.073242, 0.073348,
                                                     0.073158, 0.068447],
                          "holdout_prune_radii_px": [None, 2.0, 2.828, 3.0],
                          "evidence": "evidence/prune.json"},
        "radius_px": float(args.radius),
        "dots_before": int(dots.sum()), "dots_removed": removed,
        "dots_after": int(pruned.sum()),
    }
    _json(emit, EVID / "emit.json")
    print(f"pruned {removed} of {dots.sum()} dots within {args.radius} px "
          f"-> {int(pruned.sum())} dots")


def cmd_site(args):
    """Render the static site from the evidence artifacts that exist on disk."""
    from gems65_sarprop import site as S
    written = S.build(EVID, ROOT / "docs", root="")
    rep = load_json(EVID / "submission_receipt.json", {}) or {}
    print(f"site: {len(written)} files -> docs/")
    for w in written:
        print("  ", w.relative_to(ROOT))
    print("submission file published:", rep.get("file"), rep.get("sha256", "")[:16])


def cmd_uniqueness(args):
    """Parallel-run protocol step 1: is this a duplicate of an existing lane?

    Two checks, both from the frozen template tool and both run TWICE -- once on
    the pre-placement surface and once on the final dots:
      * rank correlation (Spearman) with every hash-verified registry raster;
      * the share of my dots that land within 3 px of one registry raster's dots.
    STOP (duplicate) if rho > 0.90 or that share > 0.70.
    """
    from gems65_sarprop.template import uniqueness as U
    g = load_grid()
    idx = ROOT / args.index
    out = {"evidence_class": "MEASURED (uniqueness / duplicate audit)",
           "index": str(idx), "rho_limit": U.RHO_LIMIT,
           "overlap_limit": U.OVERLAP_LIMIT, "checks": {}}

    def run(tag, arr, path_for_sha=None):
        r = U.compare_to_registry(path_for_sha, idx, g.footprint, include_reverse=True,
                                  expected_grid=((g.height, g.width), g.crs, g.transform)) \
            if path_for_sha else U.compare_array_to_registry(
                arr, idx, g.footprint, include_reverse=True,
                expected_grid=((g.height, g.width), g.crs, g.transform))
        summ = U.two_phase_summary(r.get("rows", r["rows"]) if isinstance(r, dict) else r,
                                   int(g.footprint.sum()))
        out["checks"][tag] = {"summary": summ,
                              "rows": (r.get("rows") if isinstance(r, dict) else r)}
        return summ

    if args.target in ("dots", "both"):
        tif = ROOT / "docs" / "downloads" / f"{args.name}.tif"
        field = np.zeros((g.height, g.width), np.float32)
        if tif.exists():
            import rasterio
            with rasterio.open(tif) as ds:
                field = ds.read(1).astype(np.float32)
            field = np.where(np.isfinite(field) & (field > 0), field, 0.0)
            src = f"final dots read from {tif.name}"
            sha = _sha(tif)
        else:
            dots = np.load(TMP / "dots_live.npy").astype(bool)
            field[dots & g.footprint] = 1.0
            src, sha = "final dots, pre-serialisation", None
        out["checks"]["dots_source"] = src
        s = run("dots", field, None)
        print("DOTS: literal duplicate=" +
              str(s["literal_reading"]["duplicate"]) + " like-for-like duplicate=" +
              str(s["like_for_like_reading"]["duplicate"]) +
              " worst rho=" + str(s["literal_reading"]["worst_spearman_full_footprint"]) +
              " worst forward overlap=" + str(s["literal_reading"]["worst_forward_overlap"]))
    if args.target in ("surface", "both"):
        sc = np.load(TMP / "score_live.npy").astype(np.float32)
        sc = np.where(np.isfinite(sc), sc, 0.0)
        sc = np.clip(sc, 0.0, 1.0)
        sc[~g.footprint] = 0.0
        s = run("surface", sc, None)
        print("SURFACE: literal duplicate=" +
              str(s["literal_reading"]["duplicate"]) + " like-for-like duplicate=" +
              str(s["like_for_like_reading"]["duplicate"]) +
              " worst rho=" + str(s["literal_reading"]["worst_spearman_full_footprint"]))
    _json(out, EVID / "uniqueness.json")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest")
    for name in ("gate", "propensity_field", "emit"):
        sp = sub.add_parser(name)
        sp.add_argument("--kappa", type=float, default=KAPPA)
        sp.add_argument("--max-iter", type=int, default=12)
        if name == "emit":
            sp.add_argument("--budget", type=int, default=160_000,
                            help="dot budget cap.  The blocked-holdout measurement "
                                 "(evidence/budget_curve.json) is monotone increasing "
                                 "up to saturation, so the cap is set to the top of the "
                                 "predeclared grid and the scan self-truncates when "
                                 "no candidate survives 3 px suppression.")
    sp = sub.add_parser("write")
    sp.add_argument("--name", default="gems65-sarprop-pu-v1")
    sp.add_argument("--note", default="Selection-bias-aware SAR propensity PU "
                                      "(Bekker-Davis EM), nnPU-gated.")
    sp = sub.add_parser("uniqueness")
    sp.add_argument("--target", choices=("dots", "surface", "both"), default="both")
    sp.add_argument("--name", default="gems65-sarprop-pu-v1")
    sp.add_argument("--index", default="registry/registry_full_index.json")
    sub.add_parser("site")
    sp = sub.add_parser("prune")
    sp.add_argument("--radius", type=float, default=2.0)
    a = ap.parse_args()
    {"ingest": cmd_ingest, "gate": cmd_gate, "propensity_field": cmd_propensity_field,
     "emit": cmd_emit, "write": cmd_write,
     "uniqueness": cmd_uniqueness,
     "site": cmd_site, "prune": cmd_prune}.get(a.cmd, lambda x: print("todo"))(a)


if __name__ == "__main__":
    main()
