"""Adjudication rules -- the single source of truth for "may this file be submitted?".

Separated from the build stage so that (a) the decision can be re-taken when new evidence arrives
without retraining, and (b) the same rule text is used by scripts/03_build_submission.py,
scripts/07_adjudicate.py, scripts/06_run_card.py and scripts/build_site.py.

The rules are the standing brief's, in priority order:

R1  A file must pass the independent validator (geometry, domain, range, no NaN inside the
    footprint, no mass on masked catalogue pixels).  Nothing is offered if this fails.
R2  A file must not be a duplicate of any registry raster: rank-correlation > 0.90 with any registry
    raster, or > 70 % of its dots within 3 px of one registry raster's dots, means lane drift and the
    file is refused.
R3  A lane whose pre-registered gate was not met is a NEGATIVE result: its experimental arm is
    logged, never promoted.
R4  No arm may be cleared for a weekly slot unless it has beaten the current holdout best -- i.e. its
    blocked-holdout pooled DTI exceeds the best blocked-holdout pooled DTI measured for any registry
    artifact on the SAME cells.  (Standing user constraint: "do not spend a submission slot on an
    idea that has not beaten the current holdout best.")
R5  If the holdout instrument is measured to be anti-correlated with live scores (stage 05), that is
    reported alongside the verdict, because it means R4 is a necessary condition measured on a
    biased proxy -- it can refuse a good candidate but cannot certify one.

R3/R4 are refusals; only a selector step with an organizer-confirmed receipt can promote.
"""

from __future__ import annotations

from typing import Any


def holdout_best_reference(calib_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Best blocked-holdout pooled DTI among registry artifacts, on the same cells."""
    rows = [r for r in (calib_rows or []) if isinstance(r.get("holdout_pooled_dti"), (int, float))]
    if not rows:
        return {"available": False, "best_dti": None, "best_raster": None, "n_compared": 0}
    best = max(rows, key=lambda r: r["holdout_pooled_dti"])
    return {"available": True, "best_dti": float(best["holdout_pooled_dti"]),
            "best_raster": best.get("raster"), "n_compared": len(rows),
            "live_score_of_best": best.get("reported_live_score"),
            "score_class_of_best": best.get("score_class", "OWNER-REPORT")}


def decide(*, arm: str, arm_holdout_dti: float | None, gate_passed: bool | None,
           validator_passed: bool, dup_verdict: dict[str, Any] | None,
           reference: dict[str, Any] | None, instrument_spearman_vs_live: float | None = None,
           is_experimental_arm: bool = True) -> dict[str, Any]:
    """Return {verdict, ok_to_download_and_submit, reason, rules_applied}."""
    rules: list[str] = []
    dup_verdict = dup_verdict or {}
    reference = reference or {}
    drift = bool(dup_verdict.get("lane_drift_detected"))
    unique = bool(dup_verdict.get("unique_submission", not drift))

    # ---- R1
    if not validator_passed:
        return {"verdict": "REFUSED-FORMAT", "ok_to_download_and_submit": False,
                "reason": "the independent validator did not pass every check; the file cannot be "
                          "submitted in any circumstance",
                "rules_applied": ["R1"]}
    rules.append("R1:pass")

    # ---- R2
    if drift or not unique:
        return {"verdict": "REFUSED-DUPLICATE", "ok_to_download_and_submit": False,
                "reason": f"lane drift: max rank-correlation "
                          f"{dup_verdict.get('max_spearman_surface')} / max 3-px dot overlap "
                          f"{dup_verdict.get('max_dot_overlap_3px')} against the registry corpus",
                "rules_applied": rules + ["R2:fail"]}
    rules.append("R2:pass")

    # ---- R3
    if is_experimental_arm and gate_passed is False:
        return {"verdict": "NEGATIVE", "ok_to_download_and_submit": False,
                "reason": "pre-registered gate NOT met (higher pooled blocked-holdout DTI overall AND "
                          "no loss in the highest-propensity tercile); logged as a negative result "
                          "per protocol, so the experimental arm is never offered for submission",
                "rules_applied": rules + ["R3:fail"]}
    if is_experimental_arm:
        rules.append("R3:pass")

    # ---- R4
    if not reference.get("available"):
        return {"verdict": "UNCERTAIN-NO-REFERENCE", "ok_to_download_and_submit": False,
                "reason": "no blocked-holdout reference measurement exists for any registry artifact "
                          "on these cells (run scripts/05_holdout_calibration.py), so rule R4 "
                          "('must have beaten the current holdout best') cannot be evaluated; refusing "
                          "rather than assuming",
                "rules_applied": rules + ["R4:unevaluable"]}
    beats = (arm_holdout_dti is not None
             and float(arm_holdout_dti) > float(reference["best_dti"]))
    if not beats:
        return {"verdict": "NOT-CLEARED-BELOW-HOLDOUT-BEST",
                "ok_to_download_and_submit": False,
                "reason": (f"blocked-holdout pooled DTI {arm_holdout_dti if arm_holdout_dti is not None else 'n/a'} "
                           f"does not exceed the best registry artifact on the same cells "
                           f"({reference['best_dti']:.5f}, {reference['best_raster']}); standing rule "
                           f"'do not spend a slot on an idea that has not beaten the current holdout "
                           f"best' therefore refuses it"),
                "rules_applied": rules + ["R4:fail"],
                "instrument_spearman_vs_live": instrument_spearman_vs_live}
    rules.append("R4:pass")

    # ---- R5 (report, never promote)
    note = ""
    if instrument_spearman_vs_live is not None and instrument_spearman_vs_live < 0:
        note = (f" CAVEAT R5: the holdout instrument is anti-correlated with owner-reported live "
                f"scores (Spearman {instrument_spearman_vs_live:+.3f}), so passing R4 on this proxy "
                f"is necessary but not sufficient; promotion still requires a selector step with an "
                f"organizer-confirmed receipt.")
    return {"verdict": "CLEARED-FOR-SELECTION", "ok_to_download_and_submit": True,
            "reason": ("all refusals cleared: format-valid, unique, gate met, and above the current "
                       "holdout best. Promotion to a weekly slot is a separate selector step "
                       "(protocol rule 6), so the download is offered but the decision is not taken "
                       "here." + note),
            "rules_applied": rules + ["R5:reported"],
            "instrument_spearman_vs_live": instrument_spearman_vs_live}
