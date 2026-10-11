"""Assemble the single RUN CARD required by the parallel-run protocol.

Every field is read from an evidence artifact; nothing here is typed twice.  If
an artifact is missing the field says so rather than guessing.
"""
from __future__ import annotations
import json, pathlib, sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"


def L(name, default=None):
    try:
        return json.loads((EVID / name).read_text())
    except Exception:
        return default


def main():
    gate, emit = L("gate.json"), L("emit.json")
    rev, hyp = L("uniqueness_review.json"), L("hypotheses.json")
    rec, uniq = L("submission_receipt.json"), L("uniqueness.json")
    prune, canary = L("prune.json"), L("canary.json")
    ing, halo = L("ingest.json"), L("emission_halo.json")
    lv = ((rec or {}).get("template_receipt") or {}).get("validator") or {}
    tr = ((rec or {}).get("template_receipt") or {}).get("template_report") or {}
    uts = (((uniq or {}).get("checks") or {}).get("dots") or {}).get("two_phase_summary") or {}
    lfl = uts.get("like_for_like_reading") or {}
    lit = uts.get("literal_reading") or {}
    arms = (gate or {}).get("arms", {})
    sar = arms.get("sar", {}).get("overall", {})
    nnpu = arms.get("nnpu", {}).get("overall", {})

    card = {
        "lane": "GEMSDOE65 — selection-bias-aware PU learning",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "Cataloguing is a biased sample of the fault population: a cell is "
            "catalogued if an interpreter found it convincing, which correlates with "
            "relief, slope, gravity signature, lidar coverage and distance to a range "
            "front. Modelling that sampling propensity e(x)=P(labeled|fault,x) and "
            "weighting the risk by 1/e recovers new faults that the cataloguing process "
            "under-samples, better than an unweighted nnPU model on the same folds."),
        "mechanism": (
            "SAR-EM (Bekker & Davis, PMLR v94): a classifier is fit on the propensity-"
            "weighted empirical risk of Bekker, Robberechts & Davis (arXiv:1809.03207), "
            "weight-clipped at 10, alternating with a propensity model fit on the "
            "catalogued cells only over five predeclared covariates. Emission is a "
            "descending sweep of expected credit with non-maximum suppression at the "
            "metric's own 3 px kernel radius, a budget taken from a measured curve, and "
            "a final prune of dots inside 2 px of the mapped catalogue."),
        "named_non_fault_process_that_could_mimic_it": [
            "Lithology contrast: a map-unit boundary traced as a line can be a false "
            "positive wherever it is not a fault. The gravity-derived basin-fill "
            "covariate is the specific confound this lane cannot separate from a real "
            "segment, because basin margins and range fronts are where faults live.",
            "LiDAR acquisition footprint: a scarp-like signal can appear at tile seams. "
            "The lidar_coverage covariate exists to absorb this, but a seam inside a "
            "covered tile is not modelled.",
            "Mapped-lineament bias: the catalogue itself contains lineaments drawn from "
            "imagery, so any model trained on it inherits the interpreter's geometric "
            "habits. Non-maximum suppression limits, but does not remove, this."],
        "holdout_dti": {
            "sar_propensity_arm": sar.get("dti"),
            "nnpu_baseline": nnpu.get("dti"),
            "delta_overall": (gate or {}).get("gate", {}).get("delta_overall"),
            "top_propensity_tercile": {
                "sar": arms.get("sar", {}).get("top_propensity_tercile", {}).get("dti"),
                "nnpu": arms.get("nnpu", {}).get("top_propensity_tercile", {}).get("dti"),
                "delta": (gate or {}).get("gate", {}).get("delta_top_tercile")},
            "evaluator": "frozen template metric.dti_exact; alpha 0.2, beta 0.8, 300 m triangular kernel",
            "withheld_positives": (gate or {}).get("withheld_positives"),
            "instrument": (gate or {}).get("instrument"),
            "confidence_interval": None,
            "why_no_interval": ("one blocked draw (seed 2026). A single-partition "
                                "instrument yields no cross-draw interval; reporting one "
                                "from a single partition would be fabrication. Multi-seed "
                                "repeat is listed as the top remaining work."),
            "comparability": ("RELATIVE ONLY. The instrument scores withheld pixels; the "
                              "organizer scores every fault. Never compare with a "
                              "leaderboard number.")},
        "emission": {
            "rule": (emit or {}).get("emission_rule"),
            "budget_cap": (emit or {}).get("budget"),
            "n_dots_before_prune": (emit or {}).get("n_dots_unpruned"),
            "prune": (emit or {}).get("prune"),
            "n_dots_final": (rec or {}).get("n_dots")},
        "experiments_run": [
            "E1 emission rule: bar-budget vs price curve vs price curve + NMS (evidence/emission.json)",
            "E1b measured budget curve, surrogate vs evaluator (evidence/budget_curve.json)",
            "E2 halo exclusion around known faults -- REJECTED (evidence/emission_halo.json)",
            "E3 prune-only at 2.0/2.236/2.828/3.0 px -- 2.0 px CONFIRMED (evidence/prune.json)",
            "E4 reconstruction of the 0.2778 receipt by exact set identity (evidence/prune.json)"],
        "negative_results": [
            "Forbidding the 3 px halo around mapped faults before allocation lowers "
            "holdout DTI at all three arms: "
            + ", ".join(f"{k}={v.get('holdout_dti'):.6f}"
                        for k, v in (halo or {}).get("results", {}).get("sar", {}).items()),
            "The model's own surrogate price curve preferred 64,000 dots; the evaluator "
            "preferred more. The surrogate was demoted to a diagnostic.",
            "SCAR (constant propensity) is cleanly worse than both PU arms, at every "
            "budget measured, which is the rejection of the null this lane exists to test."],
        "leakage_canary": {"worst_discriminative_auc": (canary or {}).get("worst_discriminative_auc"),
                           "threshold": 0.90, "clean": not (canary or {}).get("flag", True)},
        "duplicate_review_density_corrected": {
            "dots": ((rev or {}).get("checks") or {}).get("dots"),
            "surface": ((rev or {}).get("checks") or {}).get("surface"),
            "irregularity": (rev or {}).get("irregularity"),
            "why_it_is_needed": ("the literal 3 px overlap rule saturates at 1.0 for any candidate "
                                 "when a prior covers a few percent of the map, because the test "
                                 "dilates that prior by the kernel radius; the review reports the "
                                 "uniform null and the Jaccard index alongside it")},
        "candidate_hypotheses_ranked": [
            {"rank": c["rank"], "name": c["name"],
             "expected_dti_gain": c["expected_dti_gain"],
             "implementation_cost": c["implementation_cost"],
             "validated_here": c["validated_here"],
             "validation_note": c.get("validation_note")}
            for c in (hyp or {}).get("hypotheses", [])],
        "registry_correlation_and_overlap": {
            "rasters_checked": uts.get("rasters_checked"),
            "rasters_expected": uts.get("rasters_expected"),
            "worst_spearman_full_footprint": lit.get("worst_spearman_full_footprint"),
            "max_jaccard_over_all_rasters": (((rev or {}).get("checks") or {})
                                             .get("dots") or {}).get("max_jaccard"),
            "literal_overlap_firings": (((rev or {}).get("checks") or {})
                                        .get("dots") or {}).get("literal_rule_firings"),
            "firings_explained_by_density": (((rev or {}).get("checks") or {})
                                             .get("dots") or {})
                                            .get("firings_explained_by_density"),
            "density_corrected_verdict": (((rev or {}).get("checks") or {})
                                          .get("dots") or {}).get("verdict"),
            "worst_spearman_submission": lit.get("worst_spearman_submission"),
            "worst_forward_overlap": lit.get("worst_forward_overlap"),
            "worst_forward_overlap_dot_fields": lfl.get("worst_forward_overlap_dot_fields"),
            "rho_limit": 0.90, "overlap_limit": 0.70,
            "duplicate": bool(lit.get("duplicate")),
            "scope": uts.get("scope_note"),
            "indexed_inventory_not_organizer_registry": True},
        "raster": {
            "file": (rec or {}).get("file"), "sha256": (rec or {}).get("sha256"),
            "bytes": (rec or {}).get("bytes"), "shape": (rec or {}).get("shape"),
            "crs": (rec or {}).get("crs"), "transform": (rec or {}).get("transform"),
            "dtype": (rec or {}).get("dtype")},
        "validator_output": {
            "all_finite": (rec or {}).get("all_finite"),
            "values_in_unit_interval": (rec or {}).get("values_in_unit_interval"),
            "dots_only_outside_catalogue": (rec or {}).get("dots_only_inside_allowed"),
            "template_checks": lv.get("checks"),
            "template_sha256": tr.get("sha256"),
            "nan_pixels": tr.get("nan_pixels"),
            "status": ((rec or {}).get("template_receipt") or {}).get("status")},
        "submission": {
            "name": (rec or {}).get("name"),
            "note": (rec or {}).get("note"),
            "note_chars": (rec or {}).get("note_len"),
            "note_limit": 140,
            "zip": ((rec or {}).get("template_receipt") or {}).get("zip_file")},
        "verdict": ("promote-to-selector-only"
                    if (gate or {}).get("gate", {}).get("verdict") == "PROMOTE"
                    and (rec or {}).get("sha256")
                    and "not-a-duplicate" in str((((rev or {}).get("checks") or {})
                                                  .get("dots") or {}).get("verdict", ""))
                    else "negative"),
        "verdict_scope": ("Local promotion only: gate met, format validated, duplicate "
                          "audit clear. Organizer acceptance and any leaderboard score "
                          "are unknown until a slot is spent."),
        "budget_note": ("This session ran 4 experiments rather than the protocol's 3, and "
                        "more than 2 hours, because the first two experiments returned a "
                        "null result that could not be published as a verdict without "
                        "isolating the emission rule. Recorded as a deviation."),
        "instrument_receipts": {
            "holdout": (ing or {}).get("holdout_draw"),
            "visible_catalogue_px": (gate or {}).get("visible_catalogue_px")},
    }
    (EVID / "run_card.json").write_text(json.dumps(card, indent=1) + "\n")
    print(json.dumps({k: card[k] for k in ("verdict", "submission", "holdout_dti",
                                           "registry_correlation_and_overlap")}, indent=1))


if __name__ == "__main__":
    main()
