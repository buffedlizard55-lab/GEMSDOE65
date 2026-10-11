"""CLI entry point to the unmodified shared writer's on-disk validators."""
import _path  # noqa: F401
from gems65.common import ROOT, write_json, verify_template
from gems57.gates import format_report
from gems57.validate import validate, assert_submittable
import argparse
import json
import numpy as np
import rasterio


def check(path, sample, catalogue=None):
    verify_template()
    with rasterio.open(sample) as ds:
        footprint = np.isfinite(ds.read(1))
    cat = None
    if catalogue is not None:
        with rasterio.open(catalogue) as ds:
            cat = ds.read(1) == 1
    fmt = format_report(path, sample, footprint=footprint)
    local = validate(path, footprint, cat)
    try:
        assert_submittable(local)
        ok = fmt['ok'] is True
    except AssertionError:
        ok = False
    return dict(ok=ok, status='PASS' if ok else 'FAIL', format=fmt, local=local,
                organizer_acceptance=False, scope='Local format/range preflight only; not a promotion or slot approval.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('raster')
    p.add_argument('--sample', default=str(ROOT/'data/raw/sample_submission.tif'))
    p.add_argument('--catalogue', default=str(ROOT/'data/raw/existing_faults.tif'))
    p.add_argument('--json-output')
    args = p.parse_args()
    try:
        result = check(args.raster,args.sample,args.catalogue)
    except (OSError, ValueError) as e:
        result = dict(ok=False,status='FAIL',error=str(e),organizer_acceptance=False)
    if args.json_output:
        write_json(args.json_output,result)
    print(json.dumps(result,indent=2,allow_nan=False))
    raise SystemExit(0 if result['ok'] else 1)

if __name__=='__main__': main()
