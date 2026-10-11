"""Rebuild the published submission GeoTIFF from the committed dot list.

Why this exists
---------------
The artifact itself (`docs/downloads/gems65-sarprop-pu-v1.tif`) is a model
output, so it is deliberately **not** tracked in Git: the repository-wide
publication guard rejects tracked TIFFs, ZIPs and arrays, and that guard is
right -- a research site must not hand out model artifacts as if they were
cleared for release.  What *is* committed is the complete information content of
the artifact in auditable text form:

* `evidence/submission_dots.csv.gz` -- every positive pixel as `(row,col)`,
  gzipped, 197 KB, with the target SHA256 in its header;
* `evidence/submission_receipt.json` -- the grid (shape, transform, CRS, dtype),
  the submission name and note, and the SHA256 the rebuild must reproduce.

Two modes, both strict, neither of them a private fork of the writer:

``--via-template`` (default when the official bridge rasters are present)
    Rebuilds through the **frozen shared template writer**, exactly as the
    original run did, and requires the SHA256 to match the receipt.  This is the
    only mode that can claim byte identity, because the container bytes depend
    on the writer's own profile and metadata.

``--direct`` (fallback, and all CI can do)
    Writes the same field with rasterio directly and requires **pixel**
    identity with the committed dot list; the container hash is reported as
    informational and is explicitly *not* claimed to equal the receipt.  Anyone
    verifying the published file should compare pixel fields or the receipt
    hash, not a rebuild hash from this mode.

Usage:
    python scripts/reconstruct_submission.py                # byte-identical, needs data/bridge
    python scripts/reconstruct_submission.py --direct       # pixel-identical, no data needed
    python scripts/reconstruct_submission.py --check        # verify, write nothing
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RECEIPT = ROOT / "evidence" / "submission_receipt.json"
DOTS = ROOT / "evidence" / "submission_dots.csv.gz"
NAME = "gems65-sarprop-pu-v1"
OUT = ROOT / "docs" / "downloads" / f"{NAME}.tif"
BRIDGE = ROOT / "data" / "bridge"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_dots(path: Path = DOTS) -> np.ndarray:
    rows: list[tuple[int, int]] = []
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("#") or line.startswith("row,"):
                continue
            r, c = line.split(",")
            rows.append((int(r), int(c)))
    a = np.asarray(rows, dtype=np.int64)
    if a.ndim != 2 or a.shape[1] != 2 or a.shape[0] == 0:
        raise ValueError(f"malformed dot list: {path}")
    if len(set(map(tuple, a.tolist()))) != a.shape[0]:
        raise ValueError("dot list contains duplicates")
    return a


def field_from(dots: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    a = np.zeros(shape, np.float32)
    a[dots[:, 0], dots[:, 1]] = 1.0
    return a


def build_via_template(field: np.ndarray, out: Path, receipt: dict) -> dict:
    """The original code path: the frozen writer, same name, note and metadata."""
    from gems65_sarprop.template.grid import load_grid
    from gems65_sarprop.template.submission_writer import write_submission

    g = load_grid(BRIDGE)
    return write_submission(out, field, BRIDGE / "sample_submission.tif", g.footprint,
                            note=receipt["note"], name=receipt.get("name", NAME),
                            catalogue=g.catalogue,
                            metadata={"lane": "gems65 SAR-propensity PU",
                                      "emission_rule": "nms3_saturated",
                                      "arm": "sar (propensity-weighted risk)"})


def build_direct(field: np.ndarray, out: Path, receipt: dict) -> None:
    """Fallback writer: identical pixels, no claim about container bytes."""
    import rasterio

    shape = tuple(int(v) for v in receipt["shape"])
    if field.shape != shape:
        raise ValueError(f"dot list implies shape {field.shape}, receipt says {shape}")
    profile = {"driver": "GTiff", "dtype": "float32", "count": 1,
               "height": shape[0], "width": shape[1], "crs": receipt["crs"],
               "transform": rasterio.transform.Affine(*receipt["transform"]),
               "compress": "deflate", "nodata": None, "tiled": False}
    with rasterio.open(out, "w", **profile) as ds:
        ds.write(field, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild the published submission GeoTIFF.")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dots", default=str(DOTS))
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    ap.add_argument("--direct", action="store_true",
                    help="use the rasterio fallback (pixel identity, no byte-identity claim)")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting an existing artifact in the output path")
    args = ap.parse_args()

    receipt = json.loads(RECEIPT.read_text())
    want = receipt["sha256"]
    dots = load_dots(Path(args.dots))
    field = field_from(dots, tuple(int(v) for v in receipt["shape"]))
    out = Path(args.out)

    if out.exists() and not args.check and not args.force:
        print(f"{out} already exists; use --force to overwrite (the site serves this file).")
        return 2

    have_bridge = (BRIDGE / "sample_submission.tif").exists()
    mode = "direct" if (args.direct or not have_bridge) else "via-template"
    if mode == "via-template" and not have_bridge:
        print("bridge rasters missing; falling back to --direct (pixel identity only).")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / f"{NAME}.tif"
        if mode == "via-template":
            build_via_template(field, tmp, receipt)
        else:
            build_direct(field, tmp, receipt)

        got = sha256(tmp)
        import rasterio
        with rasterio.open(tmp) as ds:
            arr = ds.read(1)
        same_pixels = bool(np.array_equal(arr, field))
        print(f"mode              {mode}")
        print(f"dots in list      {dots.shape[0]:,}")
        print(f"positive pixels   {int((arr > 0).sum()):,}")
        print(f"pixels identical  {same_pixels}")
        print(f"sha256 receipt    {want}")
        print(f"sha256 rebuilt    {got}")

        if not same_pixels:
            print("MISMATCH: the rebuild does not carry the committed dot list. Refusing.",
                  file=sys.stderr)
            return 1
        if mode == "via-template" and got != want:
            print("MISMATCH: the frozen writer did not reproduce the original container.\n"
                  "That means the receipt or the dot list is wrong, or the writer changed "
                  "-- investigate, do not 'fix' the hash.", file=sys.stderr)
            return 1
        if mode == "direct":
            print("note              container bytes differ from the frozen writer's output by "
                  "design;\npixel field is identical, and only the receipt hash identifies the "
                  "published file.")
        if args.check:
            print("check only: nothing written")
            return 0
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(tmp.read_bytes())
        print(f"wrote {out} ({out.stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
