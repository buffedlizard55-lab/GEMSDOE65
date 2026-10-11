"""Fetch every registry raster listed in registry/registry_rasters.json into .cache/registry_rasters/.

Nothing binary is committed to git: the cache directory is gitignored.  Each entry is verified
three ways after download -- byte size, that rasterio can open it, and that its geometry matches
the competition grid -- and the resulting sha256 is written to registry/registry_receipt.json so a
later session can prove it is comparing against the same bytes.

Run:  python scripts/00_fetch_registry.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402

from gems65 import grid as G  # noqa: E402


def cache_dir() -> Path:
    d = Path("/home/user/.cache/registry_rasters")
    d.mkdir(parents=True, exist_ok=True)
    return d


def gh_blob_raw(repo: str, ref: str, path: str, dest: Path) -> tuple[bool, str]:
    """Resolve the blob sha via the contents API, then stream raw bytes via the blobs API."""
    listing = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}", "--jq", ".sha,.size"],
        capture_output=True, text=True)
    if listing.returncode != 0:
        return False, f"contents API failed: {listing.stderr.strip()[:200]}"
    sha, size = listing.stdout.split()
    with dest.open("wb") as fh:
        p = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw",
                            f"repos/{repo}/git/blobs/{sha}"], stdout=fh, stderr=subprocess.PIPE)
    if p.returncode != 0:
        return False, f"blob API failed: {p.stderr.decode()[:200]}"
    if dest.stat().st_size != int(size):
        return False, f"size mismatch: got {dest.stat().st_size} expected {size}"
    return True, sha


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    repo_root = G.repo_root()
    reg = json.loads((repo_root / "registry" / "registry_rasters.json").read_text())
    out_dir = cache_dir()
    receipt = []
    for entry in reg["rasters"]:
        dest = out_dir / entry["dest"]
        if dest.exists() and not args.force:
            status, blob = "cached", None
        else:
            ok, blob = gh_blob_raw(entry["repo"], entry["ref"], entry["path"], dest)
            status = "fetched" if ok else f"FAILED: {blob}"
        rec = {"dest": str(dest), "repo": entry["repo"], "path": entry["path"],
               "reported_score": entry.get("reported_score"), "score_class": entry["score_class"],
               "status": status}
        if dest.exists():
            h = hashlib.sha256(dest.read_bytes()).hexdigest()
            rec["sha256"] = h
            rec["bytes"] = dest.stat().st_size
            try:
                geo = G.check_grid(dest)
                rec["geometry_ok"] = bool(geo["shape_ok"] and geo["crs_ok"] and geo["transform_ok"])
                with rasterio.open(dest) as ds:
                    a = ds.read(1)
                rec["finite_pixels"] = int(np.isfinite(a).sum())
                rec["positive_pixels"] = int(np.nansum(np.nan_to_num(a, nan=0.0) > 0))
                rec["min"] = float(np.nanmin(a))
                rec["max"] = float(np.nanmax(a))
            except Exception as exc:
                rec["geometry_ok"] = False
                rec["error"] = str(exc)
        receipt.append(rec)
        print(f"[{status:>9s}] {entry['dest']:52s} score={entry.get('reported_score')} "
              f"geo_ok={rec.get('geometry_ok')} dots={rec.get('positive_pixels')}")
    (repo_root / "registry" / "registry_receipt.json").write_text(
        json.dumps({"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "cache_dir": str(out_dir), "rasters": receipt}, indent=2), encoding="utf-8")
    n_ok = sum(1 for r in receipt if r.get("geometry_ok"))
    print(f"[done] {n_ok}/{len(receipt)} rasters readable and grid-conformant")
    return 0 if n_ok == len(receipt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
