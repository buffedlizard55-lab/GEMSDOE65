#!/usr/bin/env python3
"""Build the live artefact: fit on the whole catalogue, emit, write, validate, certify.

This is the only script that produces a downloadable GeoTIFF.  It does not choose
anything: the shipped ranker is decided by ``registry/preregistration.json``'s
ship rule applied to ``evidence/e1_px5.json``, and the artefact is written with a
verdict field (``SHIPPABLE`` / ``DO-NOT-SUBMIT``) that the site banner reads
verbatim.

Order of operations (each step hard-fails rather than silently repairing):

1. fit the propensity with the pre-registered selection rule
   (:func:`gems65.lane.propensity_choice`) on the *whole* catalogue vs the
   independent state-geologic-map inventory;
2. fit the SAR arm and the nnPU baseline on identical data;
3. rank by the shipped arm's score field;
4. emit ``BUDGET`` dots: strict local maxima in a 3 px (300 m) NMS disk, no mass
   within 300 m of a mapped catalogue pixel (``d >= 3``);
5. write float32 EPSG:32611 with :mod:`gems57.submission_writer` in all-finite
   zeros mode -- the mode that cannot produce the portal's
   "Predicted values must be in range [0, 1]" error;
6. validate with :mod:`gems57.validate` and assert submittability;
7. compare the dots AND the surface against every accessible registry raster;
8. write the run card with an evidence class on every number.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: F401,E402

from gems57 import submission_writer, uniqueness, validate  # noqa: E402
from gems57.grid import load_grid  # noqa: E402
from gems65 import lane  # noqa: E402
from gems65.paths import (CACHE, COVARIATE_CACHE, DOWNLOADS, EVIDENCE, EXTERNAL,  # noqa: E402
                          REGISTRY, SAMPLE_SUBMISSION, ensure_dirs)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_lane import (BUDGET, EPOCHS, BATCH, HIDDEN, LR, N_UNL, EM_ITERS,  # noqa: E402
                      load_cov, measure_pi, sgmc_instrument, standardization,
                      emission_geometry, _sha)

NAME = "gems65-sar2inv-a2-38k"
NOTE = ("SAR-PU, propensity anchored on 2 public fault inventories; rank "
        "P(y|x)*(1-e(x)); 38k dots, 300m NMS, 300m peel")
STAMP = "20261011T2100Z"
REGISTRY_RASTER_DIR = Path("/home/user/ref_repos/60GEMSDOE/registry/rasters")
REGISTRY_INDEX = Path("/home/user/ref_repos/60GEMSDOE/registry/registry_index.json")


def ship_rule(e1: dict) -> dict:
    """Apply the pre-registered ship rule to the E1 receipt.  No discretion."""
    pre = json.loads((REGISTRY / "preregistration.json").read_text())
    i1 = e1["I1_hide_recover"]["scores"]
    i2 = e1["I2_sgmc_offcat"]["scores"]
    terc = e1["I1_tercile_gate"]["scores"]
    d_nb = e1["I1_hide_recover"]["paired_differences"].get("B_nnpu")
    d_12 = e1["I1_hide_recover"]["paired_differences"].get("A2_sar_1me")
    d_terc = terc["paired_differences"].get("B_nnpu")

    def lo(d):
        return float(d["ci95"][0]) if d else float("-inf")

    gate_point = float(d_nb["delta"]) > 0 if d_nb else i1["A1_sar"]["dti"] > i1["B_nnpu"]["dti"]
    gate_strict = gate_point and lo(d_nb) > 0
    tercile_ok = (float(d_terc["delta"]) >= 0) if d_terc else (
        terc["A1_sar"]["dti"] >= terc["B_nnpu"]["dti"])
    width_a2 = float(i1["A2_sar_1me"]["ci95"][1] - i1["A2_sar_1me"]["ci95"][0])
    a2_not_losing = (i1["A1_sar"]["dti"] - i1["A2_sar_1me"]["dti"]) <= width_a2
    a2_wins_i2 = i2["A2_sar_1me"]["dti"] > i2["A1_sar"]["dti"]
    if gate_strict and a2_not_losing and a2_wins_i2:
        ship, why = "A2_sar_1me", "ship rule branch 1 (A2)"
    elif gate_strict:
        ship, why = "A1_sar", "ship rule branch 2 (gate passed, A2 conditions not all met)"
    elif gate_point:
        ship, why = None, ("gate passed only as a point estimate; the paired 95% CI "
                           "includes 0, so the strict pre-registered gate did not pass")
    else:
        ship, why = None, "primary gate failed: A1_sar did not beat B_nnpu on I1"
    return {"evidence_class": "PREREGISTERED-DECISION",
            "rule_text": pre["ship_rule"]["rule"],
            "gate_point_estimate": bool(gate_point),
            "gate_strict_ci_excludes_zero": bool(gate_strict),
            "tercile_secondary_gate": bool(tercile_ok),
            "a2_within_own_ci_width_of_a1_on_i1": bool(a2_not_losing),
            "a2_width_ci_i1": width_a2,
            "a2_beats_a1_on_i2": bool(a2_wins_i2),
            "paired_delta_a1_minus_bnnpu_i1": (d_nb or {}),
            "paired_delta_a1_minus_a2_i1": (d_12 or {}),
            "paired_delta_a1_minus_bnnpu_tercile": (d_terc or {}),
            "shipped_arm": ship, "reason": why,
            "verdict": "SHIPPABLE" if ship else "DO-NOT-SUBMIT"}


def registry_index() -> tuple[list, dict]:
    """Every accessible registry raster: the 19 certified + the 43 unindexed."""
    certified = json.loads(REGISTRY_INDEX.read_text())
    cert_names = {Path(r["file"]).name for r in certified}
    rows = []
    for p in sorted(REGISTRY_RASTER_DIR.glob("*.tif")):
        rows.append({"repo": p.name.split("__")[0], "submission": p.stem,
                     "file": str(p), "sha256": _sha(p),
                     "in_certified_index": p.name in cert_names})
    meta = {"n_rasters_scanned": len(rows),
            "n_in_certified_index": sum(r["in_certified_index"] for r in rows),
            "certified_index": str(REGISTRY_INDEX),
            "raster_dir": str(REGISTRY_RASTER_DIR),
            "note": "the certified index covers 19 prior submissions; the remaining "
                    "rasters are calibration/candidate fields from the same family and "
                    "are scanned as extra comparators, flagged as not-in-certified-index"}
    return rows, meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="rebuild even if outputs exist (deletes nothing; new stamp)")
    ap.add_argument("--stamp", default=None)
    args = ap.parse_args()
    ensure_dirs()
    t0 = time.time()
    stamp = args.stamp or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    grid = load_grid()
    cov = load_cov()
    covariates = lane.PRIMARY_COVARIATES
    cat, fp = cov["catalogue"], cov["footprint"]
    ok = cov["feat_ok"] & fp

    # the gated experiment is the post-amendment one (IR-65-PROP-01); the
    # pre-amendment receipt is kept and cited for the irregularity it exposed
    e1_path = next((q for q in (EVIDENCE / "e1b_px5.json", EVIDENCE / "e1_px5.json")
                    if q.exists()), None)
    if e1_path is None:
        raise SystemExit("no experiment receipt; run scripts/run_lane.py e1b first")
    e1 = json.loads(e1_path.read_text())
    print("[gated experiment]", e1_path.name, "| pre-amendment receipt retained at",
          "evidence/e1_px5.json" if (EVIDENCE / "e1_px5.json").exists() else "(absent)")
    decision = ship_rule(e1)
    print("[ship rule]", decision["verdict"], decision["shipped_arm"], "|", decision["reason"])

    # ---- live fit on the whole catalogue ------------------------------------
    sample = lane.build_fold_sample(cov, cat, np.zeros(cat.shape, bool),
                                    covariates=covariates, n_unl=N_UNL, name="live")
    mu, sd = standardization(sample)
    sgoff = sgmc_instrument(cov)["truth"]
    ref_idx = np.flatnonzero((sgoff & ok).ravel())
    X = np.stack([cov[c].ravel().astype(np.float32) for c in covariates], axis=1)
    pi = measure_pi(cov, sgoff)["pi_lower_bound_union_of_two_inventories"]
    choice = lane.propensity_choice(sample, X[ref_idx].astype(np.float64), mu=mu, sd=sd,
                                    c=1.0, covariate_names=covariates, em_iters=EM_ITERS,
                                    em_pi_init=pi)
    print("[propensity] chosen:", choice["chosen"],
          "spearman(em, anchor) =", choice["spearman_em_vs_anchor_two_inventory"])
    idx = np.flatnonzero(ok.ravel())
    arms = {}
    for arm in ("sar", "nnpu"):
        if arm == "sar":
            if choice["chosen"] == "em":
                e_lab, e_fit, e_kind = choice["em"].e_labelled, choice["em"], choice["em"].basis_kind
            else:
                e_lab = choice["anchor"].predict_e((sample.X_lab - mu) / sd)
                e_fit, e_kind = choice["anchor"], choice["anchor"].basis_kind
        else:
            e_lab = np.full(sample.X_lab.shape[0], choice["anchor"].e_on_catalogue_mean)
            e_fit, e_kind = choice["anchor"], choice["anchor"].basis_kind
        f = lane.fit_arm(sample, arm=arm, hidden_units=HIDDEN, epochs=EPOCHS, lr=LR,
                         batch=BATCH, e_source=e_lab, pi_source=pi)
        p = lane.predict_grid(f["model"], X, f["mu"], f["sd"], grid.shape, idx)
        e = lane.predict_propensity(e_fit, X, f["mu"], f["sd"], grid.shape, idx, arm,
                                    basis_kind=e_kind)
        arms[arm] = {"p": p, "e": e, "fit": f}
        print(f"[fit {arm}] pi {f['pi']:.5f} rho {f['rho']:.6f} ebar {f['ebar']:.4f} "
              f"risk {f['risk']:.5f} {f['seconds']} s")

    score = {"A1_sar": arms["sar"]["p"],
             "A2_sar_1me": arms["sar"]["p"] * (1.0 - arms["sar"]["e"]),
             "B_nnpu": arms["nnpu"]["p"]}[decision["shipped_arm"] or "A2_sar_1me"]
    allowed = lane.allowed_mask(cov, cat, peel_px=lane.PEEL_PX)
    dots = lane.emit_dots(np.where(np.isfinite(score), score, -np.inf), allowed, BUDGET,
                          nms_px=lane.NMS_PX)
    geom = emission_geometry(dots, cov, cat)
    print("[emit]", geom)

    # the proximity control, emitted with the identical budget and geometry, so the
    # run card can state how far the lane's field is from the trivial alternative
    d_cat = ndi.distance_transform_edt(~cat)
    ctrl = lane.emit_dots(np.where(allowed, np.exp(-d_cat / 3.0), -np.inf), allowed, BUDGET,
                          nms_px=lane.NMS_PX)
    ctrl_geom = emission_geometry(ctrl, cov, cat)
    ctrl_agree = float((dots & ctrl).sum()) / BUDGET
    print("[control distance_only]", ctrl_geom, "| dot agreement with shipped field",
          round(ctrl_agree, 4))

    # ---- write the artefact --------------------------------------------------
    pred = np.zeros(grid.shape, np.float32)
    pred[dots] = 1.0
    assert np.isfinite(pred).all() and pred.min() >= 0 and pred.max() <= 1
    assert not (dots & cat).any() and not (dots & ~fp).any()
    stem = f"gemsdoe65-{NAME}-{stamp}-{hashlib.sha256(pred.tobytes()).hexdigest()[:12]}-zeros"
    out = DOWNLOADS / f"{stem}.tif"
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists; pass --stamp or --force")
    meta = {"lane": "selection-bias-aware PU learning under SAR (not SCAR)",
            "repo": "GEMSDOE65", "name": NAME, "note": NOTE,
            "shipped_arm": decision["shipped_arm"], "verdict": decision["verdict"],
            "propensity_source": choice["chosen"],
            "em_vs_anchor_spearman": choice["spearman_em_vs_anchor_two_inventory"],
            "pi_used": pi, "budget": BUDGET, "nms_px": lane.NMS_PX,
            "peel_px": lane.PEEL_PX, "covariates": list(covariates),
            "preregistration": "GEMSDOE65-PREREG-1",
            "holdout_dti_i1": {a: e1["I1_hide_recover"]["scores"][a]["dti"]
                               for a in e1["I1_hide_recover"]["scores"]},
            "holdout_dti_i2": {a: e1["I2_sgmc_offcat"]["scores"][a]["dti"]
                               for a in e1["I2_sgmc_offcat"]["scores"]}}
    submission_writer.write_submission(out, pred, SAMPLE_SUBMISSION, fp, note=NOTE,
                                       name=NAME, catalogue=cat, metadata=meta)
    receipt = validate.validate(out, footprint=fp, catalogue=cat)
    validate.assert_submittable(receipt)
    print("[validate]", json.dumps({k: receipt[k] for k in
                                    ("all_checks_passed", "sha256", "bytes",
                                     "emitted_positive_pixels", "min", "max")}))

    # ---- uniqueness against every accessible registry raster -----------------
    rows, rmeta = registry_index()
    cmp_out = uniqueness.compare_array_to_registry(pred, rows, fp,
                                                   file_sha256=receipt.get("sha256"))
    # cmp_out is the literal reading (every positive pixel is a dot, all rasters);
    # uniq_two adds the like-for-like reading restricted to dot-field comparators.
    uniq = cmp_out
    uniq_two = uniqueness.two_phase_summary(cmp_out["rows"], int(fp.sum()))
    print("[uniqueness] literal:", json.dumps(
        {k: uniq[k] for k in ("registry_rasters_checked", "registry_rasters_expected",
                              "complete_accessible_scan", "worst_spearman_full_footprint",
                              "worst_rho_submission", "worst_dot_overlap",
                              "worst_overlap_submission", "duplicate_count", "unique",
                              "stop_required")}, default=str))
    print("[uniqueness] two-phase:", json.dumps(
        {k: v for k, v in uniq_two.items() if k != "rows"}, indent=1, default=str)[:1500])

    run_card = {"evidence_class": "RUN-CARD", "generated_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "name": NAME, "note": NOTE, "stamp": stamp,
                "artifact": str(out), "artifact_sha256": receipt.get("sha256"),
                "artifact_bytes": receipt.get("bytes"),
                "verdict": decision["verdict"], "ship_decision": decision,
                "validation": receipt, "emission_geometry": geom,
                "propensity": {"chosen": choice["chosen"], "reason": choice["em_reason"],
                               "spearman_em_vs_anchor": choice[
                                   "spearman_em_vs_anchor_two_inventory"],
                               "anchor": {"c": choice["c"],
                                          "q_on_catalogue_mean": choice["anchor"].q_on_catalogue_mean,
                                          "q_on_reference_mean": choice["anchor"].q_on_reference_mean,
                                          "e_on_catalogue_mean": choice["anchor"].e_on_catalogue_mean,
                                          "e_on_reference_mean": choice["anchor"].e_on_reference_mean,
                                          "spearman_q_vs_covariates": choice[
                                              "anchor"].spearman_q_vs_covariates},
                               "em": ({"pi": choice["em"].pi, "ebar": choice["em"].ebar,
                                       "converged": choice["em"].converged,
                                       "iters": choice["em"].n_iter}
                                      if choice.get("em") else None),
                               "e_grid_quantiles": {str(k): float(v) for k, v in zip(
                                   ("p01", "p25", "p50", "p75", "p99"),
                                   np.quantile(arms["sar"]["e"][ok], [.01, .25, .5, .75, .99]))}},
                "pi_receipt": measure_pi(cov, sgoff),
                "uniqueness": {"summary": uniq, "two_phase": uniq_two, "registry_meta": rmeta,
                               "worst_rows": sorted(cmp_out["rows"],
                                                    key=lambda r: -(r.get("rho") or 0))[:5]},
                "control_distance_only": {"geometry": ctrl_geom,
                                          "dot_agreement_with_shipped_field": ctrl_agree,
                                          "note": "same budget, same NMS, same peel; no learning. "
                                                  "Reported because the sibling repository measured "
                                                  "this control beating its own headline candidate."},
                "holdout_numbers_from": str(e1_path),
                "seconds": round(time.time() - t0, 1)}
    (EVIDENCE / "live_run_card.json").write_text(
        json.dumps(run_card, indent=2, allow_nan=False, default=str) + "\n")
    print("[run card] evidence/live_run_card.json")
    print(f"[done] {run_card['seconds']} s -> {out}")


if __name__ == "__main__":
    main()
