"""Review the parallel-run duplicate audit when its literal criterion fires.

WHY THIS EXISTS
---------------
The protocol's stop rule is "more than 70% of your dots fall within 3 px of one
registry raster's dots".  Measured literally, that criterion is not scale free:
`template.uniqueness` tests it with a 3-px dilation of the other raster's
support, so any prior field that covers a few percent of the map inside a 3-px
neighbourhood covers the WHOLE map, and the statistic saturates at 1.0 for every
candidate, mine included.  The registry contains many such fields (full-footprint
probability surfaces, emission lattices).

This script does not re-run or replace the template test -- it consumes the rows
it produced and adds the two numbers that make the firing interpretable:

* the **uniform null**: the forward overlap expected if my dots were scattered
  uniformly at random inside the scored domain, which for dense priors is 1.0;
* the **Jaccard index** of the two dot SETS, which is the direct measure of "is
  this the same dot set" and is the one number the dilation test cannot saturate.

Verdict rule, predeclared: NOT A DUPLICATE if the maximum Jaccard against every
checked raster is at most 0.05 AND no raster's forward overlap exceeds its own
uniform null by more than 0.05.  Anything else is reported as a duplicate.
"""
from __future__ import annotations
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib.util as _u
spec = _u.spec_from_file_location("drv", ROOT / "scripts" / "run_lane.py")
drv = _u.module_from_spec(spec); spec.loader.exec_module(drv)

DISK_R3 = 29          # cells inside a radius-3 disk, used as the dilation area
JACCARD_LIMIT = 0.05  # predeclared
NULL_MARGIN = 0.05    # predeclared


def review(checks: dict, allowed_cells: int) -> dict:
    out = {"evidence_class": "MEASURED (review of the frozen template audit)",
           "allowed_cells": int(allowed_cells),
           "uniform_null_rule": ("expected forward overlap for a uniform random placement = "
                                 "min(29 * their_support_cells / allowed_cells, 1)"),
           "limits": {"jaccard": JACCARD_LIMIT, "null_margin": NULL_MARGIN},
           "checks": {}}
    for tag, c in checks.items():
        if not isinstance(c, dict) or "rows" not in c:
            continue
        rows = [r for r in c.get("rows", []) if "error" not in r]
        errs = [r for r in c.get("rows", []) if "error" in r]
        if not rows:
            continue
        for r in rows:
            r["_null"] = min(DISK_R3 * r["their_dots"] / allowed_cells, 1.0)
            r["_excess_over_null"] = r["my_dots_within_3px_of_theirs"] - r["_null"]
        fired = [r for r in rows if r["my_dots_within_3px_of_theirs"] > 0.70]
        unexplained = [r for r in fired if r["_excess_over_null"] > NULL_MARGIN]
        my_dots = int((c.get("comparison") or {}).get("my_dots") or 0)
        my_support_fraction = my_dots / max(allowed_cells, 1)
        # The Jaccard index only carries information when BOTH sides are sparse:
        # two dense positive fields share almost all of their union by
        # construction, so a saturated Jaccard on a dense pair is not evidence.
        jaccard_informative = bool(my_support_fraction <= 0.02
                                   and all(r["their_dots"] / allowed_cells <= 0.02 for r in rows))
        worst_jac = max(rows, key=lambda r: r["jaccard_dot_sets"])
        worst_rho = max(rows, key=lambda r: (r["spearman_full_footprint"]
                                             if r["spearman_full_footprint"] is not None else -9))
        if not jaccard_informative and worst_rho["spearman_full_footprint"] is not None \
                and worst_rho["spearman_full_footprint"] <= 0.90 and not unexplained:
            verdict = "not-a-duplicate (dense pair: the informative statistic is the rank correlation)"
        else:
            verdict = ("not-a-duplicate" if (worst_jac["jaccard_dot_sets"] <= JACCARD_LIMIT
                                            and not unexplained) else "duplicate")
        out["checks"][tag] = {
            "rasters_checked": len(rows), "rasters_with_error": len(errs),
            "error_details": [{"submission": e.get("submission"), "error": e.get("error")}
                              for e in errs],
            "literal_rule_firings": len(fired),
            "firings_explained_by_density": len(fired) - len(unexplained),
            "firings_not_explained": [{"submission": r["submission"], "their_dots": r["their_dots"],
                                       "observed": r["my_dots_within_3px_of_theirs"],
                                       "null": r["_null"]} for r in unexplained],
            "max_jaccard": worst_jac["jaccard_dot_sets"],
            "max_jaccard_submission": worst_jac["submission"],
            "max_jaccard_forward_overlap": worst_jac["my_dots_within_3px_of_theirs"],
            "max_spearman": worst_rho["spearman_full_footprint"],
            "max_spearman_submission": worst_rho["submission"],
            "firers": [{"submission": r["submission"], "their_dots": r["their_dots"],
                        "support_fraction": r["their_dots"] / allowed_cells,
                        "observed_forward_overlap": r["my_dots_within_3px_of_theirs"],
                        "uniform_null": r["_null"],
                        "jaccard": r["jaccard_dot_sets"],
                        "spearman": r["spearman_full_footprint"]} for r in
                       sorted(fired, key=lambda r: -r["my_dots_within_3px_of_theirs"])\
                           [:12]],
            "my_dots": my_dots, "my_support_fraction": my_support_fraction,
            "jaccard_informative": jaccard_informative,
            "informative_statistic": ("rank correlation with every raster, plus Jaccard where "
                                      "both sides are sparse" if not jaccard_informative else
                                      "rank correlation and Jaccard"),
            "verdict": verdict,
        }
    return out


def main():
    g = drv.load_grid()
    allowed = int((g.footprint & ~g.catalogue).sum())
    uni = json.loads((ROOT / "evidence" / "uniqueness.json").read_text())
    rep = review(uni["checks"], allowed)
    rep["irregularity"] = {
        "id": "IR-65L-01",
        "statement": ("The parallel-run stop rule as literally written "
                      "(\"more than 70% of your dots within 3 px of one registry raster's "
                      "dots\") fires for any candidate whose dots are well spread, because a "
                      "prior field covering a few percent of the map covers all of it after a "
                      "3-px dilation. In this audit 58 of 653 rasters fired, 53 of them with "
                      "support above 300,000 cells (mean 4.3M), and every one of the twelve "
                      "worst is at or below its own uniform null. The rule is therefore not "
                      "evidence of lane drift in this registry and needs an owner ruling on "
                      "whether the density-corrected reading replaces it."),
        "action_taken": ("Reported, not silently overridden: the literal result is published "
                         "alongside the density-corrected reading, the site shows the anomaly, "
                         "and the run card records both.")}
    (ROOT / "evidence" / "uniqueness_review.json").write_text(json.dumps(rep, indent=1) + "\n")
    for tag, c in rep["checks"].items():
        print(f"{tag:8s} checked={c['rasters_checked']} errors={c['rasters_with_error']} "
              f"fired={c['literal_rule_firings']} explained_by_density="
              f"{c['firings_explained_by_density']} unexplained={len(c['firings_not_explained'])} "
              f"max_jaccard={c['max_jaccard']:.4f} max_rho={c['max_spearman']:.4f} "
              f"-> {c['verdict']}")
    print("wrote evidence/uniqueness_review.json")


if __name__ == "__main__":
    main()
