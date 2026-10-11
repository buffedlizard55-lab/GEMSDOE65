#!/usr/bin/env python3
"""Stage 07 -- (re-)adjudicate every built raster against the standing rules.

Runs AFTER stages 02/03/05 so that the decision uses all available evidence: the gate
(evidence/holdout_pu.json), the duplicate check (evidence/submission_build.json) and the holdout
reference measurement (evidence/holdout_calibration.json).  Writes the verdicts back into
evidence/submission_build.json plus an audit trail in registry/adjudication.json.  No retraining,
so this can be re-run whenever new evidence lands.

Run: python scripts/07_adjudicate.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems65 import adjudicate as A  # noqa: E402
from gems65 import grid as G  # noqa: E402

REPO = Path(G.repo_root())
EVID = REPO / "evidence"


def load(p: Path, d=None):
    return json.loads(p.read_text()) if p.exists() else d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    hold = load(EVID / "holdout_pu.json", {}) or {}
    build = load(EVID / "submission_build.json", {}) or {}
    calib = load(EVID / "holdout_calibration.json", {}) or {}
    gate = hold.get("gate", {})
    pooled = hold.get("pooled", {})
    ref = A.holdout_best_reference(calib.get("rows", []))
    rho = calib.get("spearman_holdout_pooled_vs_live")

    # arm -> its own blocked-holdout pooled DTI from stage 02 (belief-field emission, 40,000 dots)
    dti_of = {
        "sar": (pooled.get("sar_erm", {}) or {}).get("dti"),
        "nnpu": ((pooled.get("nnpU_scar", {}) or {}).get("dti")
                 or (pooled.get("nnpu_scar", {}) or {}).get("dti")),
        "em": (pooled.get("sar_em_only", {}) or {}).get("dti"),
    }
    experimental = {"sar"}          # the lane's hypothesis arm; the others are baselines/controls

    audit = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "rule_text": (A.__doc__ or "").strip().splitlines()[0],
             "gate_passed": gate.get("GATE_PASSED"),
             "gate_delta_overall": gate.get("overall_delta"),
             "gate_delta_top_tercile": gate.get("top_tercile_delta"),
             "holdout_reference": ref,
             "instrument_spearman_holdout_vs_live": rho,
             "instrument_note": ("the blocked holdout is ANTI-correlated with owner-reported live "
                                 "scores because live scoring masks known-fault pixels while this "
                                 "holdout's truth IS catalogue pixels (IR-65-006); the reference "
                                 "bar of rule R4 is therefore a biased proxy bar, and it is applied "
                                 "as a refusal rule only."),
             "arms": {}}

    for name, arm in build.get("arms", {}).items():
        d = A.decide(arm=name, arm_holdout_dti=dti_of.get(name),
                     gate_passed=gate.get("GATE_PASSED"),
                     validator_passed=bool(arm.get("validator", {}).get("nan", {}).get("all_checks_passed")),
                     dup_verdict=arm.get("duplicate_check", {}).get("verdict", {}),
                     reference=ref, instrument_spearman_vs_live=rho,
                     is_experimental_arm=name in experimental)
        audit["arms"][name] = {"holdout_dti": dti_of.get(name), **d}
        arm["verdict"] = d["verdict"]
        arm["verdict_reason"] = d["reason"]
        arm["OK_TO_DOWNLOAD_AND_SUBMIT"] = d["ok_to_download_and_submit"]
        arm["adjudication"] = {"rules_applied": d["rules_applied"],
                               "holdout_dti_of_arm": dti_of.get(name),
                               "holdout_reference_best": ref.get("best_dti"),
                               "holdout_reference_raster": ref.get("best_raster"),
                               "gate_passed": gate.get("GATE_PASSED"),
                               "instrument_spearman_vs_live": rho,
                               "adjudicated_utc": audit["generated_utc"]}
        print(f"[{name:5s}] holdout_dti={dti_of.get(name)} -> {d['verdict']}  "
              f"ok_to_submit={d['ok_to_download_and_submit']}")
        print(f"        rules: {d['rules_applied']}")
        print(f"        {d['reason']}")

    if not args.dry_run:
        (EVID / "submission_build.json").write_text(json.dumps(build, indent=2) + "\n")
        (REPO / "registry" / "adjudication.json").write_text(json.dumps(audit, indent=2) + "\n")
        print(f"\n[adjudicate] wrote {EVID/'submission_build.json'} and "
              f"{REPO/'registry'/'adjudication.json'}")
    any_ok = any(a.get("OK_TO_DOWNLOAD_AND_SUBMIT") for a in build.get("arms", {}).values())
    print(f"[adjudicate] ANY FILE CLEARED FOR SUBMISSION: {any_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
