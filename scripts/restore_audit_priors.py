"""Restore the three frozen comparison rasters for forensic/duplicate audit ONLY.

These are never model inputs and never repackaged as a new submission. This is
not a claim that the full 751-blob registry has been restored or cleared.
"""
import _path  # noqa: F401
from gems65.common import ROOT, write_json
from restore_data import fetch
import json
from datetime import datetime, timezone


def main():
    pins=json.loads((ROOT/'evidence/audit_raster_pins.json').read_text())
    records=[fetch('buffedlizard55-lab/'+p['repo'],p['git_blob_sha'],p['local_path'],p['sha256'],p['bytes']) for p in pins]
    write_json(ROOT/'evidence/audit_raster_restoration.json',dict(
        checked_at=datetime.now(timezone.utc).isoformat(),files=records,
        purpose='Independent old-raster forensic and duplicate audit; never model inputs',
        complete_registry=False))
    print('Three frozen audit priors verified. Registry clearance remains incomplete.')

if __name__=='__main__':main()
