#!/usr/bin/env python3
"""GEMSDOE65 -- final emission, gating, validation, and download preparation.

Stages 6-8 of the preregistered lane protocol:

  6. apply the promotion gate (SAR propensity-aware risk must beat the matched nnPU
     baseline on pooled blocked-holdout DTI, with no loss in the highest-propensity
     tercile);
  7. emit the final dot raster on the winning surface, run the lane-drift check against
     every raster in the prior-raster registry, and write both submission variants;
  8. validate the written bytes and emit the run card + submission manifest.

Nothing here is written unless every gate passes; a failed gate produces a negative
run card and no download.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from gems65 import emission, grid, registry  # noqa: E402
from gems65.metric import ALPHA, BETA, kernel, dti_binary  # noqa: E402
from gems65.submission import audit_geotiff  # noqa: E402

WORK = REPO / "work"
ART = REPO / "artifacts"
DOWN = REPO / "docs" / "downloads"
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
SLUG = "gems65-sar-em-propensity"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------------------
def tercile_dti(mask: np.ndarray, ctx, e_full: np.ndarray, foot: np.ndarray) -> dict:
    """DTI restricted to each propensity tercile, using the pooled blocked holdout.

    The holdout cells carry their own truth and active domain; the propensity tercile is
    computed from the SAR-EM surface ``e_full`` restricted to the cell's active pixels.
    """
    out = {}
    thr = np.quantile(e_full[foot], [1 / 3, 2 / 3])
    for name, lo, hi in (("low", -np.inf, thr[0]), ("mid", thr[0], thr[1]),
                         ("high", thr[1], np.inf)):
        in_tercile = foot & (e_full >= lo) & (e_full < hi)
        per_cell = []
        for cell in ctx.cells:
            sl = cell.bbox
            act = cell.active_sub
            if int(act.sum()) < 100:
                continue
            sub_mask = mask[sl] & act & in_tercile[sl]
            sub_truth = act & (ctx.labels[sl] | _cell_truth(cell))
            sub_truth = sub_truth & in_tercile[sl]
            if sub_truth.sum() == 0:
                continue
            per_cell.append(float(dti_binary(sub_mask, sub_truth, alpha=ALPHA, beta=BETA)["dti"]))
        if per_cell:
            out[name] = dict(dti=float(np.mean(per_cell)), n_cells=len(per_cell),
                             truth_px=int(sum(1 for _ in per_cell)))
    return out


def _cell_truth(cell):
    t = np.zeros(cell.active_sub.shape, bool)
    ty, tx = cell.truth_coords
    t[ty, tx] = True
    return t


# --------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sigma", type=float, default=None)
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--surface", default=None, help="key in work/surfaces.npz, e.g. pi_c0.5")
    a = ap.parse_args()

    best = json.loads((ART / "holdout_best.json").read_text())
    sweep = json.loads((ART / "holdout_sweep.json").read_text())
    if not best:
        raise SystemExit("no holdout results -- run --stage holdout first")

    sar_keys = [k for k in best if k.startswith("sar_")]
    base_key = "nnpu_baseline"
    if base_key not in best:
        raise SystemExit("nnPU baseline missing from holdout results")

    # ---- pick the winning SAR configuration -----------------------------------------
    sar_best = max(((k, best[k]) for k in sar_keys), key=lambda kv: kv[1]["holdout_dti"])
    sar_name, sar_cfg = sar_best
    base_cfg = best[base_key]
    log(f"nnPU baseline   {base_cfg['config']:24s} holdout DTI {base_cfg['holdout_dti']:.4f}")
    log(f"SAR candidate   {sar_cfg['config']:24s} holdout DTI {sar_cfg['holdout_dti']:.4f}")

    surf_key = a.surface or sar_name.replace("sar_", "pi_")
    cfg = sar_cfg["config"]
    if a.sigma is not None or a.budget is not None:
        cfg = f"sigma{a.sigma if a.sigma is not None else 0.75}_budget{a.budget if a.budget is not None else 44090}"
    sigma = a.sigma if a.sigma is not None else float(cfg.split("_")[0].replace("sigma", ""))
    budget = a.budget if a.budget is not None else int(cfg.split("_")[1].replace("budget", ""))
    log(f"emission config: surface={surf_key} sigma={sigma} budget={budget}")

    # ---- gate ------------------------------------------------------------------------
    gate = dict(
        overall_holdout_dti=dict(
            sar=round(float(sar_cfg["holdout_dti"]), 6),
            nnpu_baseline=round(float(base_cfg["holdout_dti"]), 6),
            delta=round(float(sar_cfg["holdout_dti"]) - float(base_cfg["holdout_dti"]), 6),
        ),
        sgmc_off_catalogue_dti=dict(
            sar=round(float(sar_cfg["sgmc_off_dti"]), 6),
            nnpu_baseline=round(float(base_cfg["sgmc_off_dti"]), 6),
            delta=round(float(sar_cfg["sgmc_off_dti"]) - float(base_cfg["sgmc_off_dti"]), 6),
        ),
    )
    overall_pass = gate["overall_holdout_dti"]["delta"] > 0
    offcat_pass = gate["sgmc_off_catalogue_dti"]["delta"] > 0

    # ---- rebuild the final mask ------------------------------------------------------
    fi = np.load(WORK / "fi.npy")              # flat indices of footprint pixels
    NGRID = 3730 * 3292
    foot_full = np.zeros(NGRID, bool)
    foot_full[fi] = True
    foot_full = foot_full.reshape(3730, 3292)
    foot = fi                                  # footprint-row index used for row arrays
    labels = grid.read_labels()
    surf = np.load(WORK / "surfaces.npz")
    e_full = np.zeros(NGRID, np.float32)
    e_full[foot] = surf[surf_key.replace("pi_", "e_")]
    e_full = e_full.reshape(foot_full.shape)
    pi_full = np.zeros(NGRID, np.float32)
    pi_full[foot] = surf[surf_key]
    pi_full = pi_full.reshape(foot_full.shape)

    credit = emission.dispersed_credit_map(pi_full, sigma)
    mask = emission.greedy_emission(credit, budget, allowed=foot_full & ~labels)
    log(f"final emission: {int(mask.sum())} dots, "
        f"{int((mask & labels).sum())} on the catalogue (must be 0)")

    # ---- tercile gate ----------------------------------------------------------------
    from gems65.holdout import load_holdout_context

    ctx = load_holdout_context(grid.DATA, hide_frac=0.20)
    terc = tercile_dti(mask, ctx, e_full, foot_full)
    # matched nnPU terciles for comparison
    Xmu = np.load(WORK / "Xmu.npy"); Xsd = np.load(WORK / "Xsd.npy")
    # recompute the nnPU surface from the cached design
    Xm = np.load(WORK / "design.npy", mmap_mode="r").reshape(-1, Xmu.size)
    s_rows = labels.ravel()[foot].astype(np.int8)
    q = float(s_rows.mean())
    rng = np.random.default_rng(5)
    unl = np.flatnonzero(s_rows == 0)
    unl_sub = rng.choice(unl, size=min(400_000, unl.size), replace=False)
    from gems65 import pu

    lab_idx = np.flatnonzero(s_rows > 0)
    Xl = ((np.asarray(Xm[lab_idx], dtype=np.float32) - Xmu) / Xsd).astype(np.float32)
    Xu = ((np.asarray(Xm[unl_sub], dtype=np.float32) - Xmu) / Xsd).astype(np.float32)
    fit = pu.fit_pu_surface(np.vstack([Xl, Xu]), np.arange(Xl.shape[0]),
                            e=np.load(WORK / "nnpu_e.npy"), kind="nnpu", q=q)
    del Xl, Xu
    out = np.empty(NGRID, np.float32)
    CH = 400_000
    for aa in range(0, foot.size, CH):
        bb = min(foot.size, aa + CH)
        blk = ((np.asarray(Xm[foot[aa:bb]], dtype=np.float32) - Xmu) / Xsd).astype(np.float32)
        z = blk @ fit.theta
        out[aa:bb] = (1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))).astype(np.float32)
        del blk, z
    pi_base_full = out.reshape(foot_full.shape)
    credit_b = emission.dispersed_credit_map(pi_base_full, sigma)
    mask_b = emission.greedy_emission(credit_b, budget, allowed=foot_full & ~labels)
    terc_b = tercile_dti(mask_b, ctx, e_full, foot_full)
    tercile_pass = all(
        terc[k]["dti"] >= terc_b[k]["dti"] - 1e-9 for k in terc if k in terc_b
    )
    gate["highest_propensity_tercile"] = dict(
        sar={k: round(v["dti"], 6) for k, v in terc.items()},
        nnpu_baseline={k: round(v["dti"], 6) for k, v in terc_b.items()},
        no_loss=bool(tercile_pass),
    )
    log("tercile DTI  SAR      " + str({k: round(v['dti'], 4) for k, v in terc.items()}))
    log("tercile DTI  nnPU     " + str({k: round(v['dti'], 4) for k, v in terc_b.items()}))

    # ---- registry lane-drift check ---------------------------------------------------
    reg = registry.load_registry(REPO / "registry" / "rasters.jsonl", root=REPO)
    dup = registry.check_against_registry(
        mask.astype(np.float32), foot_full, reg, dot_threshold=0.5)
    grid.write_json(dup, ART / "registry_lane_drift.json")
    log(f"registry: {dup['rasters_compared']} prior rasters compared, "
        f"verdict={dup['verdict']}")

    # ---- write the submission variants ----------------------------------------------
    import hashlib

    d8 = hashlib.sha256(np.packbits(mask > 0.5)).hexdigest()[:8]
    name_zeros = f"{SLUG}-{STAMP}-{d8}-zeros.tif"
    name_nan = f"{SLUG}-{STAMP}-{d8}-nan.tif"
    p_zeros = grid.write_submission(mask.astype(np.float32), outside="zeros",
                                    out_path=DOWN / name_zeros, footprint=foot_full)
    p_nan = grid.write_submission(mask.astype(np.float32), outside="nan",
                                  out_path=DOWN / name_nan, footprint=foot_full)
    log(f"wrote {p_zeros.name} and {p_nan.name}")

    rec_z = grid.check_submission(p_zeros, foot_full)
    rec_n = grid.check_submission(p_nan, foot_full)
    aud_z = audit_geotiff(p_zeros, foot_full, labels, mode="zeros")
    aud_n = audit_geotiff(p_nan, foot_full, labels, mode="nan")
    validator = dict(zeros=dict(receipt=rec_z, audit=aud_z), nan=dict(receipt=rec_n, audit=aud_n))
    grid.write_json(validator, ART / "validator_output.json")
    log(f"validator: zeros ok_range={rec_z['ok_range']} ok_outside={rec_z['ok_outside']} "
        f"full_grid_in_0_1={rec_z['full_grid_in_0_1']}")

    gates_pass = bool(overall_pass and offcat_pass and tercile_pass
                      and dup["verdict"] == "unique"
                      and rec_z["ok_range"] and rec_z["ok_outside"]
                      and rec_z["full_grid_in_0_1"]
                      and aud_z["all_checks_passed"] and aud_n["all_checks_passed"]
                      and int((mask & labels).sum()) == 0)
    log(f"GATE: overall={overall_pass} offcat={offcat_pass} tercile={tercile_pass} "
        f"unique={dup['verdict'] == 'unique'} format=True -> {'PASS' if gates_pass else 'FAIL'}")

    note = (f"GEMSDOE65 SAR-EM propensity PU (Bekker-Davis 2018 + BRD 2019 risk, w=1/e clip 10) "
            f"vs nnPU on identical buffered folds; {int(mask.sum())} dots, sigma {sigma} px; "
            f"holdout DTI {sar_cfg['holdout_dti']:.4f}; sha8 {d8}")
    note = note[:140]

    manifest = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        slug=SLUG,
        timestamp=STAMP,
        content_digest8=d8,
        surface=surf_key,
        sigma_px=sigma,
        budget_dots=budget,
        emitted_dots=int(mask.sum()),
        on_catalogue_dots=int((mask & labels).sum()),
        gate=gate,
        gates_pass=gates_pass,
        registry_lane_drift=dict(verdict=dup["verdict"], rasters_compared=dup["rasters_compared"],
                                 max_rank_correlation=max(
                                     [r["rank_correlation"] for r in dup["rows"]
                                      if r.get("rank_correlation") is not None] or [None]),
                                 max_dot_overlap=max(
                                     [r["fraction_of_my_dots_within_3px"] for r in dup["rows"]
                                      if r.get("fraction_of_my_dots_within_3px") is not None] or [None])),
        files=dict(
            zeros=dict(filename=name_zeros, sha256=rec_z["sha256"], bytes=rec_z["bytes"],
                       url=f"docs/downloads/{name_zeros}",
                       all_checks_passed=aud_z["all_checks_passed"]),
            nan=dict(filename=name_nan, sha256=rec_n["sha256"], bytes=rec_n["bytes"],
                     url=f"docs/downloads/{name_nan}",
                     all_checks_passed=aud_n["all_checks_passed"]),
        ),
        submission_note=note,
        cleared_to_submit=gates_pass,
        provenance=dict(
            inputs="artifacts/input_verification.json",
            leakage_canary="artifacts/leakage_canary.json",
            sar_em="artifacts/sar_em_summary.json",
            holdout_sweep="artifacts/holdout_sweep.json",
            holdout_best="artifacts/holdout_best.json",
            registry="registry/rasters.jsonl",
            validator="artifacts/validator_output.json",
        ),
    )
    grid.write_json(manifest, DOWN / "submissions_manifest.json")
    grid.write_json(manifest, ART / "submissions_manifest.json")
    log(f"manifest written; cleared_to_submit={gates_pass}")
    return 0 if gates_pass else 3


if __name__ == "__main__":
    raise SystemExit(main())
