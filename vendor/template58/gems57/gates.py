"""On-disk format validation and compatibility access to the literal shared gate.

The format check matches the published sample representation: finite [0,1]
probabilities inside the footprint and NaN outside. A pass is still local
preflight, not organizer upload acceptance. Uniqueness delegates to
``gems57.uniqueness`` with the indexed public owner-repository inventory
manifest. This inventory is not organizer-complete; private, unlinked, external,
and otherwise inaccessible rasters may be absent. The inherited >=0.5
continuous-support and saturated-prior exemptions were unauthorized and are
retired; no second or private clearance policy remains.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import SHAPE, TRANSFORM


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_raster(path):
    with rasterio.open(path) as src:
        if src.count != 1:
            raise ValueError(f"prior has {src.count} bands, not a single prediction band")
        return src.read(1)


def format_report(path, sample, epsg=32611, cell=100.0, footprint=None):
    """Check a serialized candidate against the organizer's sample-grid mask.

    Prediction values must be finite and in [0, 1] inside the study footprint;
    the cells outside it must be NaN, matching the public specification and
    sample_submission.tif. A pass is local preflight only, never portal acceptance.
    """
    path, sample = Path(path), Path(sample)
    out = dict(path=str(path), bytes=path.stat().st_size, sha256=sha256(path))
    problems = []
    with rasterio.open(path) as src, rasterio.open(sample) as ref:
        a = src.read(1)
        ref_footprint = np.isfinite(ref.read(1))
        if footprint is None:
            fp = ref_footprint
        else:
            fp = np.asarray(footprint, bool)
        nodata_label = ("NaN" if src.nodata is not None and not np.isfinite(src.nodata)
                        else float(src.nodata) if src.nodata is not None else None)
        out.update(bands=src.count, dtype=src.dtypes[0], crs=str(src.crs), width=src.width, height=src.height,
                   bounds=list(src.bounds), ref_bounds=list(ref.bounds), transform=list(src.transform)[:6],
                   nodata=nodata_label, blocksize=list(src.block_shapes[0]), fixture_grid=ref.shape != SHAPE,
                   has_validity_mask=bool((src.dataset_mask() == 0).any()),
                   footprint_pixels=int(fp.sum()))
        if src.count != 1:
            problems.append(f"{src.count} bands, must be 1")
        if src.dtypes[0] != "float32":
            problems.append(f"dtype {src.dtypes[0]}, must be float32")
        if src.shape != ref.shape:
            problems.append(f"shape {src.shape} != reference {ref.shape}")
        if src.crs != ref.crs or src.crs is None:
            problems.append(f"CRS {src.crs} != reference {ref.crs}")
        if src.transform != ref.transform:
            problems.append("transform differs from sample_submission.tif")
        if src.bounds != ref.bounds:
            problems.append(f"bounds {src.bounds} != reference {ref.bounds}")
        if ref.shape == SHAPE:
            if src.crs is None or src.crs.to_epsg() != epsg:
                problems.append(f"CRS must be EPSG:{epsg}")
            if tuple(src.transform)[:6] != tuple(TRANSFORM)[:6]:
                problems.append("transform differs from pinned competition transform "
                                f"{tuple(TRANSFORM)[:6]}")
            if tuple(src.res) != (cell, cell):
                problems.append(f"resolution {src.res} != {(cell, cell)}")
        if fp.shape != a.shape:
            problems.append(f"footprint shape {fp.shape} != raster shape {a.shape}")
        elif not np.array_equal(fp, ref_footprint):
            problems.append("provided footprint differs from the sample_submission finite mask")
        finite = np.isfinite(a)
        inside = a[fp] if fp.shape == a.shape else np.asarray([], dtype=a.dtype)
        outside = a[~fp] if fp.shape == a.shape else np.asarray([], dtype=a.dtype)
        out.update(nan_pixels=int(np.isnan(a).sum()), infinity_pixels=int(np.isinf(a).sum()),
                   finite_inside=int(np.isfinite(inside).sum()), nan_outside=int(np.isnan(outside).sum()),
                   finite_outside=int(np.isfinite(outside).sum()))
        if np.isinf(a).any():
            problems.append(f"{int(np.isinf(a).sum())} infinite pixels are not allowed")
        if fp.shape == a.shape:
            if not np.isfinite(inside).all():
                problems.append("prediction contains NaN/non-finite values inside the study footprint")
            if not np.isnan(outside).all():
                problems.append("pixels outside the study footprint must be null/NaN as in the official sample")
        if src.nodata is None or np.isfinite(src.nodata):
            problems.append("nodata tag must be NaN to match the official sample_submission.tif")
        finite_inside = inside[np.isfinite(inside)]
        if finite_inside.size:
            lo, hi = float(finite_inside.min()), float(finite_inside.max())
            out.update(min=lo, max=hi, mean=float(finite_inside.mean()),
                       n_nonzero=int((finite_inside > 0).sum()),
                       mass=float(finite_inside.sum(dtype=np.float64)))
            if lo < 0 or hi > 1:
                problems.append(f"in-footprint values outside [0,1]: min {lo}, max {hi}")
        else:
            problems.append("study footprint has no finite prediction values")
        out["mass_outside_footprint"] = int(((a > 0) & ~fp).sum()) if fp.shape == a.shape else None
    out.update(problems=problems, ok=not problems,
               validation_class="local on-disk check against the official sample representation; not organizer upload acceptance")
    return out


def find_priors(roots, exclude=None, *, min_bytes=1000):
    found, seen = [], set()
    for root in roots:
        if not Path(root).exists():
            continue
        for path in sorted(Path(root).rglob("*.tif")):
            # Competition *inputs* are not prior submissions.  Sweeping a root that contains them
            # (the obvious mistake is passing the repository's parent so sibling checkouts are
            # covered) reads band 1 of the 19-band feature stack as if it were somebody's answer, and
            # the "prior union" then covers more pixels than the footprint itself -- which silently
            # destroys both the novelty fraction and the not-the-union test, and in the H54 build
            # emptied the novel pool to 93 px.  Measured before this exclusion: union 5,363,764 px
            # against a 5,167,373 px footprint.  IR-52-027; regression test in tests/test_gates.py.
            sp = str(path)
            if ("data/raw" in sp or path.name == "labels.tif"
                    or path.name.startswith("sample_submission")
                    or "training_features" in sp or "/external/" in sp or "data/external" in sp):
                continue
            if exclude is not None and path.resolve() == Path(exclude).resolve():
                continue
            # ... and never a *copy* of the candidate either.  scripts/refresh_feed.py stages every
            # built raster into docs/downloads/ so the site can serve it, and docs/downloads/ is one
            # of the roots this function scans; without the basename check the file is compared
            # against itself and reports "identical-to-a-prior, novel = 0", which is the one verdict
            # that would stop a legitimate submission.  Caught by scripts/check_site.py on the H55
            # build, not by reasoning about it.  IR-52-026; regression test in tests/test_gates.py.
            if exclude is not None and path.name == Path(exclude).name:
                continue
            if path.stat().st_size < min_bytes:
                continue
            if path.resolve() not in seen:
                seen.add(path.resolve())
                found.append(path)
    return found


def canonical(a):
    # Normalize only invalid/nodata prior cells, never a valid probability.
    return np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, 0).astype('<f4')


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


def uniqueness_report(emitted, priors, top=None):
    """Retired partial-inventory helper. Never clear a lane from a curated subset."""
    raise RuntimeError("Legacy novelty/0.5-support gate is retired. Use "
                       "gems57.uniqueness.compare_array_to_registry with the "
                       "indexed public owner-repository inventory in "
                       "evidence/registry_refreshed.json; not organizer-complete.")


def lane_uniqueness_report(candidate, footprint, priors=None, *, sample, phase,
                           registry_index=None, rank_limit=.90, near_limit=.70, log=None):
    """Compatibility interface delegates ONLY to the one literal shared gate.

    A caller must provide the pinned public owner-repository inventory
    manifest, not just `priors`. This inventory is not organizer-complete.
    The pre-placement SURFACE phase tests positive support too. No >=0.5
    threshold, density exemption or reverse-overlap clearance is applied.
    """
    from .uniqueness import compare_array_to_registry
    if registry_index is None:
        raise RuntimeError("A public owner-repository inventory manifest is required; partial priors cannot clear a lane")
    if priors is not None:
        raise ValueError("Pass registry_index only; legacy partial priors are not a clearance source")
    if phase not in ('surface', 'dots') or rank_limit != .90 or near_limit != .70:
        raise ValueError("literal phases/thresholds are fixed by the standing protocol")
    with rasterio.open(sample) as ref:
        expected = (ref.shape, ref.crs, ref.transform)
    if np.asarray(candidate).shape != expected[0]:
        raise ValueError('candidate shape differs from reference')
    report = compare_array_to_registry(candidate, registry_index, footprint,
        expected_grid=expected,
        progress=(lambda i, n, row: log(f'{phase} registry gate {i}/{n}')) if log else None)
    return dict(report, phase=phase, ok=report['unique'], duplicate=report['duplicate_count'] > 0,
                policy_exemptions=[], rule='literal finite >0 support at BOTH phases; no alternate policy')


def lane_report(candidate, eligible, priors=None, *, sample, phase='dots',
                registry_index=None, rank_limit=.90, near_limit=.70,
                radius_px=3.0, probe_coverage=None, log=None, coverage_cache=None):
    """Old saturation-policy entry point now fail-closed on the literal gate.

    Probe diagnostics cannot authorize exemptions. Legacy calls requesting
    an alternate saturation threshold are rejected instead of reinterpreted.
    """
    if probe_coverage is not None or radius_px != 3.0:
        raise ValueError('Saturation exemptions and radius changes are not authorized')
    return lane_uniqueness_report(candidate, eligible, priors, sample=sample,
        phase=phase, registry_index=registry_index, rank_limit=rank_limit,
        near_limit=near_limit, log=log)
