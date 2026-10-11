"""Fail closed if the published site no longer matches the committed evidence.

This is the CI half of the "obvious whether it is OK to download and submit"
requirement: if the raster's bytes, the receipt, the gate verdict and the last
site build ever disagree -- or if the promote banner were green without all three
preconditions being satisfied -- the Pages build stops instead of publishing a
stale or over-claimed page.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EVID = ROOT / "evidence"


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    problems = []
    receipt = json.loads((EVID / "submission_receipt.json").read_text())
    tif = ROOT / receipt["file"]
    if not tif.is_file():
        problems.append(f"published raster missing: {receipt['file']}")
    elif sha256(tif) != receipt["sha256"]:
        problems.append("published raster sha256 does not match its receipt")
    zip_name = tif.with_suffix(".zip")
    if not zip_name.is_file():
        problems.append(f"single-TIFF zip missing: {zip_name.name}")

    status = json.loads((DOCS / "status.json").read_text())
    for page in ("index.html", "executive-summary.html", "evidence.html",
                 "analysis-02778.html", "verification.html", "limitations.html"):
        if not (DOCS / page).is_file():
            problems.append(f"site page missing: {page}")

    gate = json.loads((EVID / "gate.json").read_text()).get("gate", {})
    if status.get("gate_verdict") != gate.get("verdict"):
        problems.append("status.json gate verdict disagrees with evidence/gate.json")

    green = {c["check"]: c["green"] for c in status.get("preconditions", [])}
    if status.get("ok_to_submit"):
        if not green.get("Blocked-holdout gate"):
            problems.append("site claims OK to submit while the gate check is not green")
        if not green.get("On-disk format validator"):
            problems.append("site claims OK to submit while the validator check is not green")
        if green.get("Parallel-run duplicate audit") is not True:
            problems.append("site claims OK to submit while the duplicate audit is not green")

    if problems:
        print("CHECK FAILED")
        for p in problems:
            print("  -", p)
        return 1
    print(f"site check OK: ok_to_submit={status.get('ok_to_submit')}, "
          f"gate={status.get('gate_verdict')}, dots={status.get('n_dots')}, "
          f"sha256={receipt['sha256'][:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
