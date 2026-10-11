"""Stage 03 -- build, validate and duplicate-check the submission rasters for every arm.

Run:  python scripts/03_build_submission.py [--dots 38000] [--a-bar 0.25] [--min-dist 2.8]

Trains the lane's models ONCE on the full visible catalogue (no holdout withholding), infers each
arm's belief field at every footprint pixel, emits an identical Poisson-disk dot field per arm,
writes the ``-nan`` / ``-zeros`` GeoTIFF pair for each, validates every file by independent re-read,
and runs the hash / pixel-agreement duplicate check against all 15 registry rasters.

Arms written:
  sar   propensity-aware ERM (arXiv:1809.03207 Definition 2, c = min(1/e, 10)) -- the lane's hypothesis
  nnpu  nnPU (Kiryo et al. 2017) baseline, prior = the Horvitz-Thompson prevalence of the same e
  em    the EM posterior alone (Bekker & Davis PMLR v94 2018 / arXiv:1809.03207 sec. 5.2), no retrain

The gate read from evidence/holdout_pu.json decides, per arm, whether the file is offered as
SUBMITTABLE or logged as a NEGATIVE RESULT.  Nothing is marked submittable unless the format
validator passed every check AND the duplicate check found no lane drift.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gems65 import adjudicate as ADJ  # noqa: E402
from gems65 import dupcheck as DC  # noqa: E402
from gems65 import emission as EMI  # noqa: E402
from gems65 import features as FT  # noqa: E402
from gems65 import grid as G  # noqa: E402
from gems65 import pu  # noqa: E402
from gems65 import submission as SUB  # noqa: E402
from scripts_lib import covariate_rows, propensity_design  # noqa: E402

CHUNK = 400_000
N_RFF = 48
N_UNLABELED = 400_000
EM_ITERS = 8
W_CLIP = 10.0
SEED = 20261011


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dots", type=int, default=38_000,
                    help="dot budget; 38000 is registry-calibrated: the two highest owner-reported "
                         "live scores in the family sit at 37,654 (0.2778) and 38,854 (0.2750) dots")
    ap.add_argument("--a-bar", type=float, default=0.25)
    ap.add_argument("--min-dist", type=float, default=2.8)
    ap.add_argument("--cat-buffer", type=int, default=3)
    ap.add_argument("--graded", action="store_true")
    ap.add_argument("--slug", default="h65-sarpu")
    args = ap.parse_args()

    t0 = time.time()
    work, repo, ddir = G.work_dir(), G.repo_root(), G.data_dir()
    z = np.load(work / "masks.npz")
    foot, labels = z["foot"], z["labels"]
    store = FT.FeatureStore(work)
    cvz = np.load(work / "covariates.npz")
    cov_full = {k: cvz[k] for k in cvz.files}

    # ---------------- training population: ALL visible catalogue positives + sampled unlabeled
    pos_flat = np.flatnonzero(labels.ravel())
    unl_pop = foot & ~labels
    n_unl_pop = int(unl_pop.sum())
    rng = np.random.default_rng(SEED)
    unl_flat = rng.choice(np.flatnonzero(unl_pop.ravel()), size=min(N_UNLABELED, n_unl_pop), replace=False)
    tr_flat = np.concatenate([pos_flat, unl_flat])
    s = np.concatenate([np.ones(pos_flat.size), np.zeros(unl_flat.size)])
    w = np.concatenate([np.ones(pos_flat.size), np.full(unl_flat.size, n_unl_pop / unl_flat.size)])
    print(f"[train] positives={pos_flat.size:,} unlabeled_sampled={unl_flat.size:,} "
          f"(population {n_unl_pop:,}, importance weight {n_unl_pop/unl_flat.size:.4f})")

    Xtr = store.rows_for_flat(tr_flat)
    Xcov = covariate_rows(cov_full, tr_flat)
    rff = pu.RFF.fit(Xtr, n_features=N_RFF, seed=SEED)
    Df = rff.design(Xtr)
    cmed = np.median(Xcov, axis=0)
    ciqr = np.maximum(np.percentile(Xcov, 75, axis=0) - np.percentile(Xcov, 25, axis=0), 1e-6)
    De = propensity_design(Xcov, cmed, ciqr)
    del Xtr, Xcov

    em = pu.fit_sar_em(Df, De, s, w, max_iter=EM_ITERS, seed=SEED, verbose=True)
    b = pu.anchor_shift(em.e_raw, s, args.a_bar)
    e_tr = pu.apply_shift(em.e_raw, b)
    pi_ht = pu.horvitz_thompson_prior(e_tr, s, w)
    c = np.minimum(1.0 / np.clip(e_tr, 1e-3, 1.0), W_CLIP)
    theta_sar = pu.fit_risk(Df, float(np.mean(s)), s, w,
                            lambda p, ss, ww: pu.propensity_weighted_risk(p, ss, c, ww), l2=1e-3)
    theta_nnpu = pu.fit_risk(Df, pi_ht, s, w,
                             lambda p, ss, ww: pu.nnpu_risk(p, ss, pi_ht, ww), l2=1e-3)
    clip_frac = float(np.mean(c >= W_CLIP - 1e-9))
    print(f"[model] EM iters={em.n_iter} converged={em.converged} a_bar={args.a_bar} "
          f"mean_e|labelled={float(np.mean(e_tr[s>0.5])):.4f} e_range=[{e_tr.min():.4f},{e_tr.max():.4f}] "
          f"pi_HT={pi_ht:.5f} clipped_weight_frac={clip_frac:.4f}")

    # ---------------- full-footprint inference for every arm
    n = store.n
    NP = G.TOTAL_PIXELS
    f_sar = np.zeros(n, np.float32); f_nnpu = np.zeros(n, np.float32); f_em = np.zeros(n, np.float32)
    e_all = np.zeros(n, np.float32)
    for a in range(0, n, CHUNK):
        bnd = min(n, a + CHUNK)
        flat = store.flat_idx[a:bnd]
        Db = rff.design(np.asarray(store.X[a:bnd], dtype=np.float64))
        Deb = propensity_design(covariate_rows(cov_full, flat), cmed, ciqr)
        f_sar[a:bnd] = pu.sigmoid(Db @ theta_sar)
        f_nnpu[a:bnd] = pu.sigmoid(Db @ theta_nnpu)
        f_em[a:bnd] = pu.sigmoid(Db @ em.theta_f)
        e_all[a:bnd] = pu.apply_shift(np.clip(pu.sigmoid(Deb @ em.theta_e), pu.E_MIN, pu.E_MAX), b)
        del Db, Deb
    def to_grid(v):
        out = np.zeros(NP, np.float32); out[store.flat_idx] = v; return out.reshape(G.SHAPE)
    belief = {
        "sar": to_grid(pu.posterior_from_models(f_sar.astype(np.float64), e_all.astype(np.float64)).astype(np.float32)),
        "nnpu": to_grid(f_nnpu),
        "em": to_grid(pu.posterior_from_models(f_em.astype(np.float64), e_all.astype(np.float64)).astype(np.float32)),
    }
    e_full = to_grid(e_all)
    np.save(work / "belief_sar.npy", belief["sar"])
    np.save(work / "belief_nnpu.npy", belief["nnpu"])
    np.save(work / "propensity_e.npy", e_full)
    print(f"[infer] belief max/min: " + ", ".join(f"{k}={v[foot].max():.3e}" for k, v in belief.items())
          + f"  ({time.time()-t0:.0f}s)")

    # ---------------- emission: identical rule and budget for every arm
    elig = EMI.eligible_offcatalogue(foot, labels, buffer_px=args.cat_buffer)
    hold = json.loads((repo / "evidence" / "holdout_pu.json").read_text())
    gate = hold["gate"]
    gate_ok = bool(gate["GATE_PASSED"])
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    receipt = json.loads((repo / "registry" / "registry_receipt.json").read_text())
    registry_paths = [Path(r["dest"]) for r in receipt["rasters"] if Path(r["dest"]).exists()]

    arms_out = {}
    for arm in ("sar", "nnpu", "em"):
        bel = belief[arm]
        dots = EMI.poisson_disk_dots(bel, elig, args.dots, args.min_dist)
        values = EMI.grade_dots(dots, bel) if args.graded else dots.astype(np.float32)
        values = SUB.sanitize(values, foot, labels, zero_on_catalogue=True)
        n_dots = int((values[foot] > 0).sum())
        digest = SUB.content_digest(values, foot)
        stem = f"gems65-{args.slug}-{arm}-a{int(args.a_bar*100):02d}-{stamp}-{digest}"
        paths = SUB.write_pair(values, foot, ddir / "sample_submission.tif", repo / "docs" / "downloads", stem)
        audits = {m: SUB.validate(Path(p), foot, labels) for m, p in paths.items()}
        dups = DC.compare(Path(paths["nan"]), registry_paths, foot, labels)
        dv = DC.verdict(dups)
        # ---- verdict: ONE implementation, src/gems65/adjudicate.py (rules R1-R5), shared with
        # scripts/07_adjudicate.py so a rebuild and a re-adjudication can never disagree.
        pooled = hold.get("pooled", {})
        dti_of = {"sar": (pooled.get("sar_erm", {}) or {}).get("dti"),
                  "nnpu": ((pooled.get("nnpU_scar", {}) or {}).get("dti")
                           or (pooled.get("nnpu_scar", {}) or {}).get("dti")),
                  "em": (pooled.get("sar_em_only", {}) or {}).get("dti")}
        calib = json.loads((repo / "evidence" / "holdout_calibration.json").read_text()) \
            if (repo / "evidence" / "holdout_calibration.json").exists() else {}
        ref = ADJ.holdout_best_reference(calib.get("rows", []))
        d = ADJ.decide(arm=arm, arm_holdout_dti=dti_of.get(arm), gate_passed=gate_ok,
                       validator_passed=bool(all(a["all_checks_passed"] for a in audits.values())),
                       dup_verdict=dv, reference=ref,
                       instrument_spearman_vs_live=calib.get("spearman_holdout_pooled_vs_live"),
                       is_experimental_arm=(arm == "sar"))
        verdict, verdict_reason = d["verdict"], d["reason"]
        ok_to_submit = d["ok_to_download_and_submit"]
        note = (f"GEMSDOE65 {arm.upper()} PU arm | a_bar={args.a_bar} | {n_dots} dots d={args.min_dist}px "
                f"offcat>={args.cat_buffer}px | holdout-gate {'PASS' if gate_ok else 'FAIL'}")[:140]
        arms_out[arm] = {
            "arm": arm, "stem": stem, "files": paths, "validator": audits,
            "duplicate_check": {"verdict": dv, "records": dups},
            "emitted_pixels": n_dots, "verdict": verdict, "verdict_reason": verdict_reason,
            "adjudication": {"rules_applied": d["rules_applied"], "holdout_dti_of_arm": dti_of.get(arm),
                             "holdout_reference_best": ref.get("best_dti"),
                             "holdout_reference_raster": ref.get("best_raster")},
            "OK_TO_DOWNLOAD_AND_SUBMIT": ok_to_submit, "submission_note": note,
            "note_length": len(note),
        }
        print(f"[arm {arm:4s}] dots={n_dots:,} validator={'PASS' if all(a['all_checks_passed'] for a in audits.values()) else 'FAIL'} "
              f"max_rho={dv['max_spearman_surface']:.4f} max_overlap3px={dv['max_dot_overlap_3px']:.4f} "
              f"unique={dv['unique_submission']} -> {verdict}")

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0, 1),
        "config": {"dots": args.dots, "a_bar": args.a_bar, "min_dist_px": args.min_dist,
                   "catalogue_buffer_px": args.cat_buffer, "graded": args.graded, "n_rff": N_RFF,
                   "n_unlabeled": N_UNLABELED, "em_iters": EM_ITERS, "weight_clip": W_CLIP, "seed": SEED},
        "model": {"em_converged": bool(em.converged), "em_iters_used": em.n_iter, "em_history": em.history,
                  "mean_propensity_labelled": float(np.mean(e_tr[s > 0.5])),
                  "propensity_min": float(e_tr.min()), "propensity_max": float(e_tr.max()),
                  "propensity_shift_b": float(b), "pi_horvitz_thompson": float(pi_ht),
                  "clipped_weight_fraction": clip_frac,
                  "propensity_coefficients": {
                      "design": ["intercept"] + [f"z_{n}" for n in ("relief", "slope", "basin_fill", "lidar_cov", "dist_range_front")]
                              + [f"z2_{n}" for n in ("relief", "slope", "basin_fill", "dist_range_front")],
                      "theta": [float(v) for v in em.theta_e]}},
        "gate_from_holdout": gate,
        "arms": arms_out,
    }
    (repo / "evidence" / "submission_build.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (repo / "registry" / "submission_build.json").write_text(json.dumps({
        "generated_utc": out["generated_utc"], "config": out["config"],
        "gate_passed": gate_ok,
        "arms": {k: {"files": v["files"], "emitted_pixels": v["emitted_pixels"], "verdict": v["verdict"],
                     "OK_TO_DOWNLOAD_AND_SUBMIT": v["OK_TO_DOWNLOAD_AND_SUBMIT"],
                     "submission_note": v["submission_note"]} for k, v in arms_out.items()},
    }, indent=2), encoding="utf-8")
    print(json.dumps({k: {"verdict": v["verdict"], "OK_TO_DOWNLOAD_AND_SUBMIT": v["OK_TO_DOWNLOAD_AND_SUBMIT"],
                          "files": v["files"]} for k, v in arms_out.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
