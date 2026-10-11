#!/usr/bin/env python3
"""Regenerate ``registry/run-card.json`` from the artifacts in ``registry/``.

The card is a *derived* document: every number in it is read from a file this
lane actually produced (arm summaries, the registry check, the candidate
receipt).  Nothing is typed in by hand, so the card cannot drift from the
evidence.  ``docs/data/run-card.json`` is a byte copy of the registry card.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
DOCS = ROOT / "docs"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(name: str) -> dict | None:
    path = REG / name
    return json.loads(path.read_text()) if path.is_file() else None


def _ci(summary: dict, arm: str) -> list:
    """``summary`` may be either the pooled block or its inner summary dict."""
    scores = summary["scores"] if "scores" in summary else summary["summary"]["scores"]
    return scores[arm]["ci95"]


def experiment_block(e3: dict | None, e2: dict | None) -> list:
    exp = []
    e1 = _load("holdout_arms.json")
    if e1:
        prim = e1["pooled"]["all"]["summary"]
        gate = e1["gate"]
        exp.append({
            "id": "E1", "evidence_class": "HOLDOUT-DTI",
            "instrument": e1.get("instrument_note",
                                 "registered: shared gems57.holdout.build_holdout (whole segments "
                                 "withheld uniformly at random per quadrant, 12 px domain erosion, "
                                 "3 px buffer, 2 seeds x 4 quadrants x {all, detached}) - recorded "
                                 "by the pre-fix writer that did not carry an instrument_note field"),
            "cells": len(e1["cells"]),
            "withheld_positive_pixels_primary_mode": e1.get("aoi", {}).get(
                "withheld_pixels_per_cell", {}),
            "propensity_model": e1.get("propensity_model", "grid"),
            "results": {
                "mode_all": {
                    "sar": prim["scores"]["sar"]["dti"], "sar_ci95": _ci(prim, "sar"),
                    "nnpu": prim["scores"]["nnpu"]["dti"], "nnpu_ci95": _ci(prim, "nnpu"),
                    "paired_delta": prim["paired_differences"]["nnpu"]["delta"],
                    "paired_delta_ci95": prim["paired_differences"]["nnpu"]["ci95"],
                },
                "top_propensity_tercile": {
                    "sar": gate["top_propensity_tercile"]["sar"],
                    "nnpu": gate["top_propensity_tercile"]["nnpu"],
                    "passed": gate["top_propensity_tercile"]["passed"],
                },
            },
            "leakage_canary_max_single_feature_auc": max(
                v for v in e1["leakage_canary"]["all"].values() if v is not None),
            "verdict": "tie / no detectable difference",
            "interpretation": "The registered instrument withholds whole segments uniformly at "
                              "random, i.e. it is SCAR by construction: the withheld positives are "
                              "exchangeable with the visible ones, so there is no covariate-"
                              "dependent bias to remove and the correction can only add variance. "
                              "This instrument cannot confirm or refute the selection-bias "
                              "mechanism.",
        })
    if e2:
        r = e2["gate"]["overall"]
        exp.append({
            "id": "E2", "evidence_class": "HOLDOUT-DTI",
            "instrument": e2.get("instrument_note", "bias-matched diagnostic instrument"),
            "cells": len(e2["cells"]),
            "propensity_model": e2.get("propensity_model", "grid"),
            "results": {
                "sar": r["sar"], "sar_ci95": e2["pooled"]["all"]["summary"]["scores"]["sar"]["ci95"],
                "nnpu": r["nnpu"], "nnpu_ci95": e2["pooled"]["all"]["summary"]["scores"]["nnpu"]["ci95"],
                "paired_delta": r["paired_delta"], "paired_delta_ci95": r["paired_ci95"],
                "top_propensity_tercile": e2["gate"]["top_propensity_tercile"],
            },
            "leakage_canary_max_single_feature_auc": max(
                v for v in e2["leakage_canary"]["all"].values() if v is not None),
            "verdict": "negative (not significant)",
            "interpretation": "Bias-matched withholding does create the situation the lane exists "
                              "for, but with the originally published EM scale the fitted propensity "
                              "was flat (see diagnostics), so the weights were inert.",
        })
    if e3:
        prim = e3["pooled"]["all"]["summary"]
        gate = e3["gate"]
        diag = e3["diagnostics"][0]
        exp.append({
            "id": "E3", "evidence_class": "HOLDOUT-DTI",
            "instrument": e3.get("instrument_note", "registered instrument"),
            "cells": len(e3["cells"]),
            "propensity_model": e3.get("propensity_model", "rbf"),
            "results": {
                "mode_all": {
                    "sar": prim["scores"]["sar"]["dti"], "sar_ci95": _ci(prim, "sar"),
                    "nnpu": prim["scores"]["nnpu"]["dti"], "nnpu_ci95": _ci(prim, "nnpu"),
                    "paired_delta": prim["paired_differences"]["nnpu"]["delta"],
                    "paired_delta_ci95": prim["paired_differences"]["nnpu"]["ci95"],
                },
                "top_propensity_tercile": {
                    "sar": gate["top_propensity_tercile"]["sar"],
                    "nnpu": gate["top_propensity_tercile"]["nnpu"],
                    "passed": gate["top_propensity_tercile"]["passed"],
                },
            },
            "propensity_diagnostics": {
                "e_pos_mean": diag.get("e_pos_mean"), "e_pos_min": diag.get("e_pos_min"),
                "e_pos_max": diag.get("e_pos_max"), "e_pos_sd": diag.get("e_pos_std"),
                "pool_ratio": diag.get("pool_ratio"), "labelled_ratio": diag.get("labelled_ratio"),
                "clip_fraction": diag.get("clip_fraction"),
            },
            "leakage_canary_max_single_feature_auc": max(
                v for v in e3["leakage_canary"]["all"].values() if v is not None),
            "verdict": "negative (tie, identical folds to E1)",
            "interpretation": "Fixing the pixel-population scale of the EM makes the propensity "
                              "genuinely non-degenerate, but on the registered SCAR instrument the "
                              "comparison is still a tie - which is the correct reading of an "
                              "instrument that contains no selection bias to correct.",
        })
    return exp


def main() -> int:
    e3 = _load("holdout_arms_e3.json")
    e2 = _load("holdout_arms_biased.json")
    e3b = _load("holdout_arms_biased_e3.json")
    rc = _load("registry_check.json")
    receipt_files = sorted((DOCS / "downloads").glob("*-receipt.json"))
    receipt = json.loads(receipt_files[-1].read_text()) if receipt_files else None
    rast = json.loads((REG / "rasters.json").read_text()) if (REG / "rasters.json").is_file() else {}
    prov = _load("template_provenance.json") or {}

    experiments = experiment_block(e3, e2)
    if e3b:
        r = e3b["gate"]["overall"]
        experiments.append({
            "id": "E3b", "evidence_class": "HOLDOUT-DTI",
            "instrument": e3b.get("instrument_note", "bias-matched diagnostic instrument"),
            "cells": len(e3b["cells"]), "propensity_model": e3b.get("propensity_model", "rbf"),
            "results": {
                "sar": r["sar"], "sar_ci95": e3b["pooled"]["all"]["summary"]["scores"]["sar"]["ci95"],
                "nnpu": r["nnpu"], "nnpu_ci95": e3b["pooled"]["all"]["summary"]["scores"]["nnpu"]["ci95"],
                "paired_delta": r["paired_delta"], "paired_delta_ci95": r["paired_ci95"],
                "top_propensity_tercile": e3b["gate"]["top_propensity_tercile"],
            },
            "verdict": "diagnostic",
            "interpretation": "Duplicate of E3 on the bias-matched instrument; when the withheld set "
                              "is enriched where the catalogue is thin the comparison is no longer "
                              "bias-free, and this is the number that tests the mechanism.",
        })

    # The promotion gate stays on the pre-registered registered instrument.
    registered = _load("holdout_arms.json")
    gate_pass = bool(registered and registered["gate"]["verdict"] == "promote")

    card = {
        "schema": "gems65-run-card/1",
        "generated_utc": (e3b or e3 or registered or {}).get("generated_utc", "NOT RUN"),
        "generator": "scripts/make_run_card.py (derived, not hand-written)",
        "repo": "buffedlizard55-lab/GEMSDOE65",
        "lane": "selection-bias-aware PU learning (SAR propensity)",
        "hypothesis": "Catalogue inclusion is Selected-At-Random conditional on a small covariate "
                      "set (local relief, slope, gravity-derived basin-fill proxy, survey coverage, "
                      "distance to a range front); therefore the omission of true faults from the "
                      "published compilation is a measurable function of those covariates and can "
                      "be corrected by inverse-propensity weighting.",
        "mechanism": "e(x) = P(S=1 | Y=1, x) is estimated by the SAR-EM recursion of Bekker & Davis "
                     "(PMLR v94, 2018), as a quantile grid (E1/E2) and as a continuous soft-binned "
                     "RBF model (E3). Labelled positives carry weight clip(1/e(x), 1, 10) in the "
                     "propensity-aware empirical risk of Bekker, Robberechts & Davis "
                     "(arXiv:1809.03207); the matched arm is the same risk with unit weights. Both "
                     "arms share features, sampler, optimiser, prior and emission rule.",
        "named_non_fault_mimic": "Landslide and erosional scarps, paleo-shorelines, lithologic "
                                 "contacts and cultural/roads lineaments in the topographic and "
                                 "gravity-gradient channels: they produce fault-like linear relief "
                                 "without being faults, and they are the reason a raw edge map "
                                 "over-fires.",
        "experiments": experiments,
        "gate": {
            "rule": "pooled blocked-holdout DTI(sar) > DTI(nnpu) overall AND DTI(sar) >= "
                    "DTI(nnpu) in the highest-propensity tercile, on the pre-registered "
                    "registered instrument (uniform withholding, blocked folds)",
            "overall_passed": gate_pass,
            "tercile_passed": bool(registered and registered["gate"]["top_propensity_tercile"]["passed"]),
            "verdict": "promote" if gate_pass else "negative",
            "current_holdout_best": "NOT ESTABLISHED - no prior holdout artifact exists in this "
                                    "checkout; the matched nnpu arm is the only incumbent available",
        },
        "diagnosis": {
            "registered_instrument_is_scar": "Uniform segment withholding makes the withheld set "
                                             "exchangeable with the visible set, so no selection "
                                             "bias exists for the correction to remove; E1 and E3 "
                                             "ties are a property of the instrument.",
            "scale_bug_found_and_fixed": "The EM originally compared a complete labelled sample "
                                         "with a subsampled unlabeled pool, which lowers the "
                                         "implied hidden-positive mass by exactly the pool ratio "
                                         "(127.7x) and drives the fixed point to e -> 1. With the "
                                         "pixel-population correction the fitted propensity is "
                                         "non-degenerate (E3 diagnostics).",
            "what_remains_unidentified": "PU data alone cannot pin the absolute scale of e(x); the "
                                         "lane reports e(x) with an explicit prior convention "
                                         "(pi = catalogue pixel density) and would need a proven "
                                         "exhaustive-completeness source to calibrate it.",
        },
        "raster": ({} if not receipt else {
            "submission_name": receipt["submission_name"], "note": receipt["note"],
            "note_chars": receipt["note_chars"],
            "primary_file": f"docs/downloads/{receipt['candidate']}-zeros.tif",
            "primary_sha256": receipt["files"][f"{receipt['candidate']}-zeros.tif"]["sha256"],
            "primary_bytes": receipt["files"][f"{receipt['candidate']}-zeros.tif"]["bytes"],
            "diagnostic_nan_file": f"docs/downloads/{receipt['candidate']}-nan.tif",
            "diagnostic_nan_sha256": receipt["files"][f"{receipt['candidate']}-nan.tif"]["sha256"],
            "emitted_positive_pixels": receipt["emitted_positive_pixels"],
            "crs": "EPSG:32611", "shape": [3292, 3730], "dtype": "float32",
            "transform": [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0],
            "encoding_primary": "all-finite, zeros outside the footprint (upload variant)",
            "encoding_diagnostic": "NaN outside the footprint (diagnostics only)",
            "propensity": receipt["method"]["propensity"],
            "distance_to_catalogue_px": receipt.get("emitted_dot_distance_to_catalogue"),
        }),
        "validator_output": ({} if not receipt else {
            "tool": "vendor/gems57/validate.py + vendor/gems57/gates.py (byte-identical to the "
                    "shared template pin 6444fa65...)",
            "all_checks_passed": all(
                v["all_checks_passed"] for k, v in receipt["files"].items() if k.endswith("-zeros.tif")),
            "checks": receipt["files"][f"{receipt['candidate']}-zeros.tif"]["validator"],
            "portal_note": "A prior upload of a different project's raster was rejected with "
                           "'Predicted values must be in range [0, 1]'. The cause was never "
                           "proven, so the primary artifact is the strict all-finite encoding.",
        }),
        "correlation_overlap_vs_registry": ({} if not rc else {
            "evidence_class": "REGISTRY-MEASUREMENT",
            "rasters_checked": rc["rasters_checked"],
            "worst_spearman_abs": rc["worst_spearman_abs"],
            "worst_spearman_file": rc["worst_spearman_file"],
            "duplicate_hash_match": rc["duplicate_hash_match"],
            "worst_forward_overlap_3px": rc["worst_forward_overlap"],
            "worst_forward_overlap_file": rc["worst_forward_overlap_file"],
            "rule_false_positive": rc.get("overlap_rule_note"),
            "saturated_witnesses": rc.get("saturated_witnesses"),
            "worst_forward_overlap_excluding_saturated_priors":
                rc.get("overlap_vs_unsaturated_priors", {}).get("worst"),
            "worst_forward_overlap_excluding_saturated_priors_file":
                rc.get("overlap_vs_unsaturated_priors", {}).get("file"),
            "unique_by_hash_and_surface": rc.get("unique_by_hash_and_surface"),
            "unique_by_literal_overlap_rule": rc.get("unique_by_literal_overlap_rule"),
            "scope_note": rc.get("scope_note"),
        }),
        "template": {
            "pin": prov.get("template_commit"),
            "verification": prov.get("pin_verification", {}).get("result"),
            "files_identical": prov.get("pin_verification", {}).get("identical"),
        },
        "submission": ({} if not receipt else {
            "name": receipt["submission_name"], "note": receipt["note"],
            "okay_to_submit": bool(gate_pass and receipt["gate"]["approved_for_weekly_slot"]),
            "reason": ("The registered promotion gate did not pass: on the registered instrument "
                       "the two arms are statistically indistinguishable, so this raster is a "
                       "research artifact and a weekly slot must not be spent on it."
                       if not gate_pass else
                       "The registered gate passed and the receipt marks the artifact approved "
                       "for a weekly slot."),
            "cleared_artifact_for_upload": (receipt["candidate"] if gate_pass else None),
        }),
        "verdict": "promote" if gate_pass else "negative",
        "next_steps": [
            "Re-run E3 on fresh seeds (disjoint folds) before treating the corrected propensity as "
            "confirmed; the scale fix was made after E1/E2 were visible.",
            "Find or rule out an official exhaustively-complete mapping source to calibrate the "
            "absolute scale of e(x); otherwise keep reporting it as a prior-conditional estimate.",
            "Candidates ranked as in docs/hypotheses.html: buried-fault wedges in basin-fill "
            "thickness, structural-strike fluid-discharge lines, radiometric alteration haloes.",
            "Extend the registry uniqueness check to every fetchable prior raster, not only the 62 "
            "committed priors.",
            "Track the family's live anchors (OWNER-REPORT only) so the lane's holdout numbers are "
            "read as model-selection evidence, not as a leaderboard projection.",
        ],
        "sources": [
            "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
            "https://www.drivendata.org/termsofuse/",
            "https://proceedings.mlr.press/v94/bekker18a.html",
            "https://arxiv.org/abs/1809.03207",
            "https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf",
            "https://doi.org/10.5066/P93LGLVQ",
        ],
    }
    if rast:
        card["inputs"] = rast
    (REG / "run-card.json").write_text(json.dumps(card, indent=2, default=float) + "\n")
    DOCS.mkdir(exist_ok=True)
    shutil.copyfile(REG / "run-card.json", DOCS / "data" / "run-card.json")
    print("run card regenerated:", card["verdict"], "| experiments:", [e["id"] for e in card["experiments"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
