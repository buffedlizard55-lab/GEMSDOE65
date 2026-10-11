#!/usr/bin/env python3
"""Restore the hash-pinned inputs this lane needs, from public mirrors.

What this script does
---------------------
1. Sparse-clones the *owner's own public sibling repositories* (they are this
   project's family of mirrors) and copies the pinned bytes into ``data/``.
2. Verifies every copied file against the sha256/size pins in
   ``evidence/input_pins.json`` before it is used.
3. Refuses to continue on a mismatch.  Nothing is silently repaired.

What this script is **not**
---------------------------
* It is not an organizer download.  The competition data page is login-walled;
  these bytes are owner-supplied mirrors (the pins say so explicitly) and are
  treated as integrity-pinned, **not** organizer-authenticated.
* It does not bypass authentication, scrape a leaderboard, or fetch any page of
  ``drivendata.org``.

Usage::

    python3 scripts/restore_inputs.py [--dest data] [--check]

``--check`` verifies whatever is already present and exits non-zero on a
mismatch without copying anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PINS = REPO_ROOT / "evidence" / "input_pins.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path: Path, pin: dict) -> list[str]:
    problems = []
    if not path.is_file():
        return [f"{path}: missing"]
    size = path.stat().st_size
    if "bytes" in pin and pin["bytes"] != size:
        problems.append(f"{path}: size {size} != pinned {pin['bytes']}")
    digest = sha256(path)
    if pin.get("sha256") and pin["sha256"] != digest:
        problems.append(f"{path}: sha256 {digest} != pinned {pin['sha256']}")
    return problems


def sparse_clone(repo: str, ref: str, paths: list[str], workdir: Path) -> Path:
    dest = workdir / repo.split("/")[-1]
    url = f"https://github.com/{repo}.git"
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1",
                    "--revision", ref, url, str(dest)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    subprocess.run(["git", "sparse-checkout", "init", "--cone"], cwd=dest, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    subprocess.run(["git", "sparse-checkout", "set", *paths], cwd=dest, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    subprocess.run(["git", "checkout"], cwd=dest, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest", type=Path, default=REPO_ROOT / "data")
    ap.add_argument("--check", action="store_true",
                    help="verify present files only; copy nothing")
    args = ap.parse_args()
    dest = args.dest.resolve()

    pins = json.loads(PINS.read_text(encoding="utf-8"))
    problems: list[str] = []
    if args.check:
        for item in pins["files"]:
            problems += verify(dest / item["dest"], item)
        for p in problems:
            print("FAIL", p)
        print("checked", len(pins["files"]), "pinned files")
        return 1 if problems else 0

    groups: dict[tuple, list[dict]] = {}
    for item in pins["files"]:
        groups.setdefault((item["repo"], item["ref"], tuple(item["sparse"])), []).append(item)

    with tempfile.TemporaryDirectory(prefix="gems65_restore_") as tmp:
        work = Path(tmp)
        for (repo, ref, sparse), items in groups.items():
            print(f"[restore] {repo}@{ref[:8]} -> {len(items)} file(s)")
            src_root = sparse_clone(repo, ref, list(sparse), work)
            for item in items:
                target = dest / item["dest"]
                target.parent.mkdir(parents=True, exist_ok=True)
                if "parts" in item:
                    with open(target, "wb") as out:
                        for part in item["parts"]:
                            out.write((src_root / part).read_bytes())
                else:
                    shutil.copy2(src_root / item["path"], target)
                found = verify(target, item)
                if found:
                    problems += found
                else:
                    print(f"[ok] {item['dest']} ({target.stat().st_size} bytes)")

    for p in problems:
        print("FAIL", p)
    if problems:
        print("\nRestore FAILED: pins did not match. Do not model on these bytes.")
        return 1
    print("\nAll pinned inputs restored and verified. "
          "Bridge provenance: integrity-pinned mirrors, NOT organizer-authenticated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
