"""Fetch every prior submission raster listed in the pinned registry index.

The index (``registry/registry_full_index.json``) is a third-party inventory:
it was built by a sibling session sweeping 56 repositories of the same owner,
de-duplicating by sha256.  It is NOT an organiser artifact and it is NOT
authoritative -- the organiser publishes no file list.  It is used here only so
the uniqueness check has a concrete, hash-pinned peer set that can be re-derived.

Sources are fetched from the GitHub *blob* API by the blob sha recorded in the
index, so a rewritten file at the same path cannot silently substitute.

Usage:  python scripts/fetch_registry.py [--limit N] [--dest DIR]
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import subprocess
import sys

INDEX = pathlib.Path("registry/registry_full_index.json")
OWNER = "buffedlizard55-lab"


def gh_raw(repo: str, blob: str, dest: pathlib.Path) -> bool:
    """Fetch one blob.  Returns True on success.  Uses the authenticated gh CLI."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    # NOTE: the blobs endpoint does not honour the raw media types from this
    # sandbox (all of application/vnd.github.raw, .raw+json and .v3.raw return
    # HTTP 404 for a blob that is demonstrably present).  The JSON + base64 form
    # is used instead.  Verified 2026-10-11: 404 with the header, 200 without.
    r = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/blobs/{blob}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if r.returncode != 0:
        return False
    try:
        payload = json.loads(r.stdout)
        raw = base64.b64decode(payload["content"], validate=False)
    except Exception:
        return False
    if not raw.startswith(b"II*\x00"):
        # a GeoTIFF must start with the little-endian TIFF magic
        return False
    dest.write_bytes(raw)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dest", default="/tmp/gems65_registry")
    args = ap.parse_args()

    idx = json.loads(INDEX.read_text())
    global OWNER
    OWNER = idx.get("owner", "buffedlizard55-lab")
    rasters = idx["rasters"]
    if args.limit:
        rasters = rasters[: args.limit]
    dest = pathlib.Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    ok = miss = 0
    for i, r in enumerate(rasters, 1):
        repo = f"{OWNER}/{r['repo_first']}" if "/" not in r["repo_first"] else r["repo_first"]
        out = dest / f"{r['sha256'][:16]}.tif"
        if gh_raw(repo, r["blob"], out):
            ok += 1
        else:
            miss += 1
            print(f"MISS {repo} {r['sources'][0]}", flush=True)
        if i % 25 == 0:
            print(f"  {i}/{len(rasters)} ok={ok} miss={miss}", flush=True)
    print(f"DONE registry fetch: ok={ok} miss={miss} of {len(rasters)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
