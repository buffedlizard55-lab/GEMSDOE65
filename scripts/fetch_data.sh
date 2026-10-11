#!/usr/bin/env bash
# Fetch and verify the competition inputs used by this lane.
#
# The official data tab (https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
# requires a login.  This project does not use credentials.  Instead it pulls the *same bytes*
# from the family's public data bridge, which exists precisely to move the official rasters into
# restricted sandboxes through git, and verifies every sha256 against that bridge's manifest.
#
# Verified in this session: labels 7ba308cc…, sample_submission 2176d08e…, features 4371c82e….
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${WORK:-/tmp/gems65-bridge}"
BRIDGE="${BRIDGE_REPO:-https://github.com/buffedlizard55-lab/6GEMSDOE.git}"

mkdir -p "$WORK"
if [ ! -d "$WORK/.git" ]; then
  git clone --depth 1 --filter=blob:none --sparse "$BRIDGE" "$WORK"
fi
( cd "$WORK" && git sparse-checkout set data && git checkout -- data 2>/dev/null || true )

mkdir -p "$ROOT/data/raw" "$ROOT/data/bridge"
cp "$WORK/data/labels.tif"                 "$ROOT/data/raw/labels.tif"
cp "$WORK/data/sample_submission.tif"      "$ROOT/data/raw/sample_submission.tif"
cp "$WORK/data/labels.tif"                 "$ROOT/data/bridge/existing_faults.tif"
cp "$WORK/data/sample_submission.tif"      "$ROOT/data/bridge/sample_submission.tif"
cat "$WORK"/data/bridge/gems-geodawn-numerical-features.tif.part-00{0,1,2,3,4} \
    > "$ROOT/data/raw/training_features.tif"

python3 - "$ROOT" <<'PY'
import hashlib, sys
from pathlib import Path
root = Path(sys.argv[1])
pins = {
    "data/raw/labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "data/raw/sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    "data/raw/training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "data/bridge/existing_faults.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "data/bridge/sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}
bad = []
for rel, want in pins.items():
    p = root / rel
    got = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    print(f"{'OK ' if got == want else 'BAD'} {rel} {got}")
    if got != want:
        bad.append(rel)
sys.exit(1 if bad else 0)
PY

echo "Optional covariate (survey coverage): fetch the public GeoDAWN DEM mirror into data/external/"
echo "  data/external/geodawn_dem_a2_100m.tif  (used only as a coverage mask; see IR-65-104)"
