#!/usr/bin/env bash
# Place the official competition rasters on the official grid, hash-verified.
#
#   data/bridge/existing_faults.tif   425,830 B   sha256 7ba308cc...ae4093
#   data/bridge/labels.tif            425,830 B   sha256 7ba308cc...ae4093  (byte-identical)
#   data/bridge/sample_submission.tif 1,599,597 B sha256 2176d08e...54d35cbc
#   data/training_features.tif    418,912,844 B   sha256 4371c82e...123bc5   (19 bands)
#
# PROVENANCE -- read this before trusting the bytes.
#
#  * The canonical origin is the DrivenData data tab
#    https://www.drivendata.org/competitions/306/competition-doe-gems/data/
#    which is login-walled.  This sandbox has no competition account and the
#    host is unreachable from here (verified: curl returns 000).
#  * The bytes are therefore restored through a *third-party public mirror*:
#    the repository `buffedlizard55-lab/GEMSDOE` at commit
#    c0c06ac82178f26b94fce3397036ef8f12a2f3a0, directory `data/bridge/`, which
#    itself records the Dropbox mirrors printed on the official data tab and the
#    sha256 pins it measured on a GitHub-hosted runner in 2026-09-14.
#  * Matching a mirror hash establishes byte identity WITH THE MIRROR.  It is
#    not an organiser receipt.  Every downstream claim in this repository is
#    scoped accordingly, and this limitation is repeated on the site.
#
# Usage:  bash scripts/download_official_data.sh [--into-only]
#   --into-only   skip the network entirely and only verify/report what is here
set -euo pipefail
cd "$(dirname "$0")/.."

REPO=${REPO:-buffedlizard55-lab/GEMSDOE}
REF=${REF:-c0c06ac82178f26b94fce3397036ef8f12a2f3a0}
FEATURE_PARTS="000 001 002 003 004"
FEATURE_PREFIX="data/bridge/gems-geodawn-numerical-features.tif.part"
SHA_FEATURES="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5"
BYTES_FEATURES=418912844
SHA_FAULTS="7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093"
SHA_SAMPLE="2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc"
INTO_ONLY=0
[ "${1:-}" = "--into-only" ] && INTO_ONLY=1

mkdir -p data/bridge .cache/featparts

fetch() {  # fetch <repo-path> <blob-out>
  local path="$1" out="$2"
  [ -s "$out" ] && { echo "  have $(basename "$out")"; return 0; }
  local sha
  sha=$(gh api "repos/$REPO/contents/$path?ref=$REF" --jq .sha)
  gh api "repos/$REPO/git/blobs/$sha" -H "Accept: application/vnd.github.raw" > "$out"
  echo "  fetched $(basename "$out") $(stat -c%s "$out") B"
}

verify() {  # verify <file> <sha> [bytes]
  local f="$1" want="$2" wantb="${3:-}"
  local got; got=$(sha256sum "$f" | cut -d' ' -f1)
  if [ -n "$wantb" ] && [ "$(stat -c%s "$f")" != "$wantb" ]; then
    echo "FAIL $f size $(stat -c%s "$f") != $wantb" >&2; exit 1
  fi
  [ "$got" = "$want" ] && echo "OK   $f  $got" || { echo "FAIL $f got $got want $want" >&2; exit 1; }
}

if [ "$INTO_ONLY" = 0 ]; then
  echo "== fetching official rasters through the pinned public mirror =="
  fetch "data/bridge/existing_faults.tif" data/bridge/existing_faults.tif
  fetch "data/bridge/example_submission.tif" data/bridge/sample_submission.tif
  for i in $FEATURE_PARTS; do
    fetch "$FEATURE_PREFIX-$i" ".cache/featparts/part-$i"
  done
  cat .cache/featparts/part-000 .cache/featparts/part-001 .cache/featparts/part-002 \
      .cache/featparts/part-003 .cache/featparts/part-004 > data/training_features.tif
fi

cp data/bridge/existing_faults.tif data/bridge/labels.tif
echo "== verifying =="
verify data/bridge/existing_faults.tif "$SHA_FAULTS" 425830
verify data/bridge/labels.tif         "$SHA_FAULTS" 425830
verify data/bridge/sample_submission.tif "$SHA_SAMPLE" 1599597
[ -s data/training_features.tif ] && verify data/training_features.tif "$SHA_FEATURES" "$BYTES_FEATURES" \
  || echo "NOTE data/training_features.tif absent; re-run without --into-only"
echo "== placing template-expected names =="
python3 - <<'PY'
import pathlib, shutil
b = pathlib.Path("data/bridge")
for src, dst in [("existing_faults.tif", "existing_faults.tif"),
                 ("sample_submission.tif", "sample_submission.tif")]:
    if (b / src).exists():
        print("  present:", b / src)
PY
python3 scripts/verify_grid.py
