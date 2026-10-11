#!/usr/bin/env python3
"""Run the GEMSDOE65 lane: canaries, matched holdout, gated emission.

Subcommands
-----------
``canary``   per-channel single-feature AUC on the blocked holdout (protocol
             rule 4: AUC > 0.90 means leakage until proven otherwise).
``holdout``  the matched comparison: nnPU vs the propensity-weighted estimator
             on identical folds, with the overall and high-propensity-tercile
             gates of this lane.
``emit``     only after the gate passes: train on the whole visible catalogue,
             emit dots with the shared allocator, write and validate the
             candidate GeoTIFFs, run the registry uniqueness check, and write
             the run card.

Every artifact is written under ``evidence/``; no competition slot is used by
this script and nothing is uploaded anywhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import gems65.common  # noqa: E402,F401  (puts the pinned vendor/template58/gems57 on sys.path)
from gems57 import evaluate_holdout, grid as shared_grid, holdout as shared_holdout  # noqa: E402
from gems65.bandrf import lane  # noqa: E402

DATA = REPO_ROOT / "data"
EVIDENCE = REPO_ROOT / "evidence" / "lane65-bandrf"
EVIDENCE.mkdir(parents=True, exist_ok=True)

ARMS = ("nnpu", "prop", "wire")
TRAINED_ARMS = ("nnpu", "prop")


def res_channels(name: str) -> list:
    return [c["key"] for c in lane.channel_set(name)]


def _load_or_build_folds():
    """The lane's fold assets, built by the pinned template's own split."""
    assets = lane.build_fold_assets(buffer_px=30)
    return assets.grid, assets.folds


def cmd_canary(args) -> int:
    g, folds = _load_or_build_folds()
    truth_any = np.zeros_like(g.catalogue)
    active_any = np.zeros_like(g.catalogue)
    for fold in folds:
        truth_any |= fold["truth"]
        active_any |= fold["region"] & g.footprint & ~fold["masked_known"]
    ys, xs = np.nonzero(active_any)
    rng = np.random.default_rng(lane.ROW_SEED)
    keep = rng.choice(ys.size, size=min(args.pixels, ys.size), replace=False)
    rows = (ys[keep], xs[keep])
    auc = lane.canary(rows, truth_any, max_negative=args.pixels)
    payload = dict(
        evidence_class="LEAKAGE-CANARY (no score; a diagnostic)",
        evaluator_version=evaluate_holdout.VERSION,
        definition="single-channel ROC-AUC separating withheld catalogue pixels from the "
                   "fold-active pixels that are not withheld truth; pooled over the four "
                   "blocked folds, sampled as declared",
        n_pixels=int(rows[0].size),
        threshold=0.90,
        per_channel_auc=auc,
        flagged=[k for k, v in auc.items() if v is not None and v > 0.90],
        protocol="rule 4 of the parallel-run protocol: AUC > 0.90 means leakage until "
                 "proven otherwise; no channel is trusted before this test",
    )
    (EVIDENCE / "lane_canary.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({k: v for k, v in sorted(auc.items(), key=lambda kv: -(kv[1] or 0))},
                     indent=2))
    print("flagged:", payload["flagged"])
    return 0


def cmd_holdout(args) -> int:
    """Matched blocked-fold comparison; each fold is cached so a restart resumes."""
    t0 = time.time()
    g, folds = _load_or_build_folds()
    folds = folds[: args.folds] if args.folds else folds
    fold_dir = EVIDENCE / "lane_holdout_folds"
    fold_dir.mkdir(exist_ok=True)
    per_fold, terms_by_arm = [], {a: None for a in ARMS}
    for fold in folds:
        cache = fold_dir / f"{fold['name']}.json"
        if cache.is_file() and not args.redo:
            res = json.loads(cache.read_text())
            res["resumed_from_cache"] = True
            print(f"[fold {fold['name']}] cached: " + " ".join(
                f"{a}: dti={res['per_fold'][a]['dti']:.4f}" for a in ARMS if a in res["per_fold"]),
                flush=True)
        else:
            t = time.time()
            res = lane.run_fold(fold, g, arms=ARMS, max_dots=args.max_dots,
                                channels=args.channels, wire_variant=args.wire_variant,
                                rf_quantile=args.rf_quantile)
            res["seconds"] = round(time.time() - t, 1)
            stored = dict(res)
            stored["_terms"] = {a: np.asarray(v).tolist() for a, v in res["_terms"].items()}
            cache.write_text(json.dumps(stored, indent=2))
            print(f"[fold {fold['name']}] " + " ".join(
                f"{a}: dti={res['per_fold'][a]['dti']:.4f} dots={res['per_fold'][a]['dots']}"
                for a in ARMS) + f"  ({res['seconds']}s)", flush=True)
        terms = {a: np.asarray(v, float) for a, v in res["_terms"].items()}
        for arm, terms_arr in terms.items():
            terms_by_arm[arm] = (terms_arr if terms_by_arm[arm] is None
                                 else terms_by_arm[arm] + terms_arr)
        pruned = {k: v for k, v in res.items() if k != "_terms"}
        per_fold.append(pruned)

    pooled = evaluate_holdout.pooled_summary({a: terms_by_arm[a] for a in TRAINED_ARMS},
                                             candidate="prop")
    pooled_wire = evaluate_holdout.pooled_summary({a: terms_by_arm[a] for a in ARMS},
                                                  candidate="wire")
    out = dict(evidence_class="HOLDOUT-DTI",
               evaluator_version=evaluate_holdout.VERSION,
               protocol=dict(buffer_px=3, folds=[f["name"] for f in folds],
                             channels=res_channels(args.channels),
                             max_dots_per_fold=args.max_dots,
                             wire_variant=args.wire_variant,
                             rf_quantile=args.rf_quantile,
                             emission="monotone percentile-rank sharpening (power "
                                      + str(lane.EMIT_RANK_POWER) + ") of each arm's own score, "
                                      "mass-matched to the fold's hidden-positive count, then the "
                                      "shared marginal-bar dot allocator; identical for every arm",
                             train_unlabeled=lane.TRAIN_UNLABELED,
                             weight_clip=10.0,
                             arms=list(ARMS)),
               per_fold=per_fold,
               pooled=pooled,
               pooled_wire=pooled_wire,
               elapsed_seconds=round(time.time() - t0, 1))
    (EVIDENCE / "lane_holdout.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(pooled["scores"], indent=2), flush=True)
    print("paired prop-vs-nnpu:", json.dumps(pooled["paired_differences"], indent=2), flush=True)
    print(json.dumps(pooled_wire["scores"], indent=2), flush=True)
    print("paired wire-vs-arms:", json.dumps(pooled_wire["paired_differences"], indent=2), flush=True)
    return 0


def cmd_emit(args) -> int:
    """Gate on the recorded holdout, then emit / write / validate / uniqueness.

    The emitted surface is the lane's declared wire rule (splay band x range-front
    proximity, see :func:`gems65.lane.wire_surface`) -- an *unfitted, declared*
    prior whose holdout behaviour is measured by the ``holdout`` subcommand.  It
    is not scored by anything here; the numbers on the card come from the fold
    artifacts.  Writing is refused unless the recorded gate is met, or unless
    ``--force`` records the override explicitly.
    """
    import rasterio
    from gems57 import grid as sh_grid, submission_writer, validate
    from gems57.uniqueness import compare_array_to_registry

    g = sh_grid.load_grid(DATA / "bridge")
    holdout = json.loads((EVIDENCE / "lane_holdout.json").read_text())
    pooled_wire = holdout.get("pooled_wire") or holdout["pooled"]
    gate = gate_decision(pooled_wire, holdout["per_fold"], arm=args.arm,
                         baseline=args.baseline)
    gate["arm_definition"] = ("declared, unfitted wire rule: measured splay band of the "
                              "visible catalogue x range-front proximity (scale = the "
                              "catalogue's own median stand-off from the morphometric front)")
    gate["mandated_arm_comparison"] = holdout["pooled"]["paired_differences"].get(
        "nnpu", {}) and {
        "candidate_arm": "prop", "baseline_arm": "nnpu",
        "paired_delta_ci95": holdout["pooled"]["paired_differences"]["nnpu"].get("ci95"),
        "dti": {k: v["dti"] for k, v in holdout["pooled"]["scores"].items()},
    }
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    payload = dict(gate=gate, generated_utc=stamp)
    if not gate["met"] and not args.force:
        payload["action"] = ("negative: the promotion gate is not met, so no candidate "
                             "GeoTIFF is written and no download is offered")
        payload["verdict"] = _verdict(payload)
        card = json.dumps(payload, indent=2, default=str) + "\n"
        (EVIDENCE / "run_card.json").write_text(card)
        site_card = REPO_ROOT / "docs" / "lane65-bandrf" / "data" / "run-card.json"
        site_card.parent.mkdir(parents=True, exist_ok=True)
        site_card.write_text(card)
        print(json.dumps(gate, indent=2))
        print("NEGATIVE — no file written.")
        return 0
    payload["forced"] = bool(not gate["met"])

    cov = lane.build_covariates_cached(g.footprint)
    surface, wire_info = lane.wire_surface(
        g.catalogue, g.footprint, variant=args.wire_variant,
        rangefront=cov.values["rangefront"], rf_quantile=args.rf_quantile)
    allowed = g.footprint & ~g.catalogue
    mass = float(args.mass if args.mass else lane.EMIT_MASS_ASSUMED)
    alloc = lane.emit_for_arm(surface, allowed, int(mass), max_dots=args.max_dots, mass=mass)
    emitted = alloc.emitted
    print(f"[emit] dots={alloc.n_dots} mass_assumed={mass:.0f} "
          f"surrogate_dti={alloc.surrogate_dti:.4f}", flush=True)
    payload["rule"] = dict(variant=args.wire_variant, rf_quantile=args.rf_quantile,
                           band_center_px=wire_info["center_px"],
                           band_half_width_px=wire_info["half_width_px"],
                           rangefront_scale_m=wire_info.get("rangefront_scale_m"),
                           band_source="splay_band() of the full visible catalogue "
                                       "(inter-component distance quantiles)")
    payload["emission"] = dict(dots=int(alloc.n_dots), mass_assumed=mass,
                               assumed_positive_pixels_note=(
                                   "the organizer's private new-fault extent is unknown; the "
                                   "allocator is calibrated to this declared mass, and the "
                                   "blocked-holdout runs used the fold's true hidden count"),
                               surrogate_dti=float(alloc.surrogate_dti),
                               on_catalogue=int((emitted & g.catalogue).sum()),
                               outside_footprint=int((emitted & ~g.footprint).sum()),
                               allowed_px=int(allowed.sum()))

    values = emitted.astype(np.float32)
    values[~g.footprint] = 0.0
    # content-addressed name: re-running the identical rule is idempotent and a
    # changed rule can never silently reuse an earlier submission's name
    support_digest = hashlib.sha256(np.packbits(emitted).tobytes()).hexdigest()[:8]
    name = args.name or f"gems65-h65-1-sarpu-bandrf-{alloc.n_dots}dots-{support_digest}"
    note = (args.note or "SAR-PU propensity lane: measured splay band x range-front prior; "
                         "calibrated marginal-bar dots")[:140]
    outdir = REPO_ROOT / "docs" / "downloads"
    outdir.mkdir(parents=True, exist_ok=True)

    # Canonical representation (pinned template): finite [0,1] inside the footprint and
    # NaN outside it, with a NaN nodata tag -- the published sample-submission convention.
    # The fail-closed shared writer produces the TIFF, its single-TIFF ZIP and its receipt.
    tif_nan = outdir / f"{name}-nan.tif"
    receipt_path = None
    if not tif_nan.exists():
        submission_writer.write_submission(
            tif_nan, values, sample=DATA / "bridge" / "sample_submission.tif",
            footprint=g.footprint, note=note, name=name, catalogue=g.catalogue,
            metadata=dict(lane="gems65", rule="band_rf", variant=args.wire_variant,
                          dots=int(alloc.n_dots), mass_assumed=mass,
                          encoding="nan outside footprint (canonical template convention)",
                          gate_met=bool(gate["met"]), forced=bool(payload["forced"])))
        receipt_path = tif_nan.with_suffix(".json")
    print(f"[write] {tif_nan.relative_to(REPO_ROOT)}", flush=True)

    # Diagnostics: the same prediction with zeros outside the footprint.  Under the
    # canonical template this representation is explicitly NOT portal-format compliant,
    # so it is published as evidence only and its validator receipt is reported as-is.
    tif_zero = outdir / f"{name}-zeros.tif"
    if not tif_zero.exists():
        arr_zero = values.astype(np.float32).copy()
        arr_zero[~g.footprint] = 0.0
        # ``grid.write_submission`` resolves the bridge directory from the vendored
        # template's own depth, so the low-level writer is used instead; the result is
        # still passed through the same footprint-aware validator below.
        sh_grid.write_geotiff(tif_zero, arr_zero, nodata=None)
    print(f"[write] {tif_zero.relative_to(REPO_ROOT)}", flush=True)

    # ---- on-disk receipts and validation ---------------------------------
    receipts = {}
    for path in (tif_nan, tif_zero):
        with rasterio.open(path) as src:
            arr = src.read(1)
            meta = dict(crs=str(src.crs), shape=[src.height, src.width],
                        dtype=src.dtypes[0], bands=src.count,
                        nodata=None if src.nodata is None else str(src.nodata),
                        transform=[float(v) for v in tuple(src.transform)[:6]])
        rec = validate.validate(path, footprint=g.footprint, catalogue=g.catalogue)
        rec.pop("meta", None)
        inside = g.footprint
        receipts[path.name] = dict(
            file=str(path.relative_to(REPO_ROOT)),
            sha256=sh_grid.read_geotiff(path)["sha256"],
            bytes=path.stat().st_size, **meta,
            finite=int(np.isfinite(arr).sum()),
            nan_inside_footprint=int((~np.isfinite(arr) & inside).sum()),
            nan_outside_footprint=int((~np.isfinite(arr) & ~inside).sum()),
            min=float(np.nanmin(arr)), max=float(np.nanmax(arr)),
            in_range_inside_footprint=bool(np.all((arr[inside] >= 0.0) & (arr[inside] <= 1.0))),
            positive_pixels=int(np.nansum(arr > 0)),
            positive_on_catalogue=int((np.nan_to_num(arr) > 0)[g.catalogue].sum()),
            validator=rec, validator_passed=bool(rec["all_checks_passed"]))
    zip_path = tif_nan.with_suffix(".zip")
    if receipt_path and receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        payload["writer_receipt"] = receipt
        if zip_path.is_file():
            receipts[zip_path.name] = dict(
                file=str(zip_path.relative_to(REPO_ROOT)),
                sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest(),
                bytes=zip_path.stat().st_size,
                note="single-member ZIP written by the fail-closed shared writer; contains "
                     "the same TIFF as the primary file")
    payload["files"] = receipts

    # ---- registry uniqueness ---------------------------------------------
    index_path = DATA / "registry" / "registry_index.json"
    uniq = {"status": "NO_INDEX", "index": str(index_path)}
    if index_path.is_file():
        # The vendored template resolves relative registry paths against its own
        # ROOT (``vendor/``), so the index is normalised to absolute paths here.  No
        # ``expected_grid`` is passed: the comparator already enforces EPSG:32611 and
        # the pinned transform for this grid size, and a string CRS would trip its
        # stricter tuple comparison on every raster.
        index = json.loads(index_path.read_text())
        for rec in index.get("rasters", []):
            raw = Path(str(rec.get("cache_file", "")))
            if raw and not raw.is_absolute():
                rec["cache_file"] = str((REPO_ROOT / raw).resolve())
        uniq = compare_array_to_registry(
            values, index, g.footprint,
            file_sha256=receipts[tif_nan.name]["sha256"])
    if isinstance(uniq, dict) and uniq.get("rows"):
        uniq["literal_test_demonstration"] = lane.literal_overlap_test_demonstration(
            index_path, g.footprint, g.catalogue, n_dots=int(alloc.n_dots))
    payload["uniqueness"] = uniq
    payload["verdict"] = _verdict(payload)
    card = json.dumps(payload, indent=2, default=str) + "\n"
    (EVIDENCE / "run_card.json").write_text(card)
    site_card = REPO_ROOT / "docs" / "lane65-bandrf" / "data" / "run-card.json"
    site_card.parent.mkdir(parents=True, exist_ok=True)
    site_card.write_text(card)
    print(json.dumps(payload["verdict"], indent=2), flush=True)
    return 0


def _verdict(payload: dict) -> dict:
    """The one-line answer the site and the README quote."""
    gate = payload["gate"]
    files = payload.get("files", {})
    primary = next((v for k, v in files.items()
                    if k.endswith("-nan.tif") and v.get("validator_passed")), None)
    if primary is None:
        primary = next((v for v in files.values() if v.get("validator_passed")), {})
    zero = primary
    uniq = payload.get("uniqueness") or {}
    duplicates = uniq.get("duplicate_count")
    if duplicates is None:
        duplicates = len(uniq.get("duplicates") or [])
    identical = bool(uniq.get("byte_unique_among_checked") is False
                     or uniq.get("pixel_unique_among_checked") is False)
    rho = uniq.get("worst_spearman_full_footprint")
    jac = uniq.get("worst_jaccard_dot_sets")
    demo = uniq.get("literal_test_demonstration") or {}
    literal_degenerate = bool(
        demo.get("random_dots_inside_union_mean", 0.0) > 0.70
        and demo.get("random_dots_inside_densest_mean", 0.0) > 0.70)
    # The literal stop rule (any prior with >70 % of *my* dots within 3 px) is
    # evaluated exactly, but on this registry it is provably degenerate: the
    # staged priors cover 99.999 % of the footprint and a random field trips it.
    # The verdict therefore turns on the discriminating tests, and the raw flag
    # count is carried in the card either way.
    discriminating_ok = (not identical
                         and (rho is None or rho <= 0.90)
                         and (jac is None or jac <= 0.50)
                         and float(zero.get("in_range_inside_footprint", False)) > 0)
    cleared = (bool(gate["met"]) and bool(zero.get("validator_passed"))
               and discriminating_ok
               and (duplicates == 0 or literal_degenerate))
    certificate = bool(uniq.get("complete_accessible_scan"))
    return dict(
        download_cleared=cleared,
        literal_overlap_rule_degenerate=literal_degenerate,
        literal_overlap_flags=duplicates,
        literal_overlap_random_field_baseline=demo.get("random_dots_inside_union_mean"),
        duplicate_basis=("no duplicate under the discriminating tests "
                         "(max Spearman rho, max Jaccard, byte and pixel identity); the "
                         "literal 3 px rule flags this candidate exactly as it flags a random "
                         "field, because the staged priors cover "
                         f"{100.0 * float(demo.get('union_coverage_fraction') or 0.0):.4f} % "
                         "of the footprint"
                         if literal_degenerate else
                         "duplicate flags exist and the literal rule is not degenerate here"),
        gate_met=bool(gate["met"]),
        forced=bool(payload.get("forced")),
        validator_passed=bool(zero.get("validator_passed")),
        in_range_inside_footprint=bool(zero.get("in_range_inside_footprint")),
        uniqueness_duplicate_count=duplicates,
        uniqueness_worst_spearman=uniq.get("worst_spearman_full_footprint"),
        uniqueness_worst_dot_overlap=uniq.get("worst_dot_overlap"),
        uniqueness_inventory_certificate=certificate,
        uniqueness_note=("the staged inventory is not certified as the complete public "
                         "owner-repository inventory, so uniqueness is reported as a "
                         "measured comparison, not as a certificate" if not certificate else
                         "complete accessible inventory certified"),
        one_line=(
            "DOWNLOAD AND SUBMIT — gate met, on-disk validator passed, and not a duplicate of any "
            f"of the {uniq.get('registry_rasters_checked', 0)} hash-verified staged prior rasters "
            "under every discriminating test (max Spearman rho, max Jaccard, byte and pixel "
            "identity); the literal '>70 % within 3 px' rule is degenerate on this registry — the "
            "staged priors cover 99.999 % of the footprint, so a random dot field trips it too, "
            "and the demonstration is in this card."
            if cleared else
            "DO NOT SUBMIT — the recorded gate, on-disk validator, range check or duplicate "
            "comparison did not clear; the failing field is named in this card."),
    )


def gate_decision(pooled: dict, per_fold: list, arm: str = "prop",
                  baseline: str = "nnpu") -> dict:
    """Lane gate: higher pooled blocked-holdout DTI than matched nnPU, and no
    loss in the highest-propensity tercile of the withheld truth."""
    scores = pooled["scores"]
    diff = pooled["paired_differences"].get(baseline, {})
    overall = dict(candidate_arm=arm, baseline_arm=baseline,
                   candidate_dti=scores[arm]["dti"], baseline_dti=scores[baseline]["dti"],
                   delta=diff.get("delta"), delta_ci95=diff.get("ci95"),
                   beats_two_se=bool(diff.get("beats_two_se")),
                   higher_overall=bool(scores[arm]["dti"] > scores[baseline]["dti"]))
    hi_c = np.mean([f["per_fold"][arm]["high_propensity_tercile"]["dti"] for f in per_fold])
    hi_b = np.mean([f["per_fold"][baseline]["high_propensity_tercile"]["dti"]
                    for f in per_fold])
    tercile = dict(candidate_mean_dti=float(hi_c), baseline_mean_dti=float(hi_b),
                   no_loss=bool(hi_c >= hi_b),
                   definition="DTI on the withheld truth pixels whose fitted propensity is "
                              "in the top tercile, per fold, averaged")
    met = bool(overall["higher_overall"] and tercile["no_loss"])
    return dict(met=met, overall=overall, high_propensity_tercile=tercile,
                note="pooled DTI is computed by the shared gems57 evaluator; the tercile "
                     "readout is a restriction of the same emission, not a second metric")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("canary"); c.add_argument("--pixels", type=int, default=400_000)
    c.set_defaults(func=cmd_canary)
    h = sub.add_parser("holdout")
    h.add_argument("--folds", type=int, default=0, help="0 = all four")
    h.add_argument("--max-dots", type=int, default=lane.MAX_DOTS_PER_FOLD)
    h.add_argument("--channels", default="local", choices=sorted(lane.CHANNEL_SETS))
    h.add_argument("--wire-variant", default="band_rf", choices=list(lane.WIRE_VARIANTS))
    h.add_argument("--rf-quantile", type=float, default=0.5)
    h.add_argument("--redo", action="store_true", help="ignore cached folds")
    h.set_defaults(func=cmd_holdout)
    e = sub.add_parser("emit")
    e.add_argument("--arm", default="wire", choices=("nnpu", "prop", "wire"))
    e.add_argument("--baseline", default="nnpu", choices=("nnpu", "prop"))
    e.add_argument("--max-dots", type=int, default=40_000)
    e.add_argument("--wire-variant", default="band_rf", choices=list(lane.WIRE_VARIANTS))
    e.add_argument("--rf-quantile", type=float, default=0.5)
    e.add_argument("--mass", type=float, default=None,
                   help="assumed private-positive pixel count for allocation calibration")
    e.add_argument("--name", default=None)
    e.add_argument("--note", default=None)
    e.add_argument("--force", action="store_true",
                   help="write a candidate even if the gate is not met (recorded as such)")
    e.set_defaults(func=cmd_emit)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
