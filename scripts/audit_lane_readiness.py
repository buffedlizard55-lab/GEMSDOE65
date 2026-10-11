#!/usr/bin/env python3
"""Fail-closed readiness audit for the requested SAR-EM experiment lane.

This is an input/tool presence check only. It does not run a holdout, validate a TIFF,
create predictions, or replace the shared evaluator/writer.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_ALIASES = {
    "feature_stack": ("data/training_features.tif", "data/numeric_features.tif", "data/gems-geodawn-numerical-features.tif"),
    "labels": ("data/labels.tif", "data/existing_faults.tif", "data/faults.tif"),
    "sample_template": ("data/sample_submission.tif", "data/example_submission.tif"),
}
SHARED_TOOLS = ("evaluate_holdout.py", "submission_writer.py")
RASTER_REGISTRY_CANDIDATES = (
    "registry/rasters.json",
    "registry/rasters.jsonl",
    "data/evidence/rasters.json",
)


def _present_alias(root: Path, choices: tuple[str, ...]) -> dict:
    present = next((item for item in choices if (root / item).is_file()), None)
    return {"status": "present" if present else "missing", "path": present, "accepted_paths": list(choices)}


def _find_named_tool(root: Path, filename: str) -> str | None:
    for path in root.rglob(filename):
        if ".git" in path.parts or path.is_dir():
            continue
        return path.relative_to(root).as_posix()
    return None


def audit(root: Path) -> dict:
    root = root.resolve()
    data = {name: _present_alias(root, paths) for name, paths in DATA_ALIASES.items()}
    tools = {}
    for filename in SHARED_TOOLS:
        path = _find_named_tool(root, filename)
        tools[filename] = {"status": "present" if path else "missing", "path": path}
    registry = next((item for item in RASTER_REGISTRY_CANDIDATES if (root / item).is_file()), None)
    checks = {
        "competition_inputs": data,
        "required_shared_tools": tools,
        "prior_raster_registry": {
            "status": "present" if registry else "missing",
            "path": registry,
            "accepted_paths": list(RASTER_REGISTRY_CANDIDATES),
        },
    }
    blockers = []
    for name, result in data.items():
        if result["status"] != "present":
            blockers.append(f"missing competition input: {name}")
    for filename, result in tools.items():
        if result["status"] != "present":
            blockers.append(f"missing required shared tool: {filename}")
    if not registry:
        blockers.append("missing prior-raster registry")
    prerequisites_present = not blockers
    return {
        "audit_time_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "gate": "prerequisites-present" if prerequisites_present else "negative",
        "checks": checks,
        "blockers": blockers,
        "action": (
            "Presence checks pass only. Run the shared preregistered holdout, leakage canaries, uniqueness checks, and validator; this audit is not promotion and does not authorize a TIF."
            if prerequisites_present
            else "Stop. Do not train, generate, offer, or submit a TIF. Restore the shared inputs/tools/registry first."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, indent=2))
    return 0 if result["gate"] == "prerequisites-present" else 2


if __name__ == "__main__":
    raise SystemExit(main())
