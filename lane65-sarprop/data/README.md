# data/

Small, committed inputs and the recipe for the large ones.

## Committed here

| File | Bytes | Why it is in Git |
|---|---|---|
| `bridge/sample_submission.tif` | 1,599,597 | defines the footprint and the exact grid every submission must match |
| `bridge/existing_faults.tif` | 425,830 | the published catalogue; byte-identical to `labels.tif` |
| `bridge/labels.tif` | 425,830 | the organiser's training labels (nodata −1 ⇒ inside the footprint) |

`existing_faults.tif` and `labels.tif` are byte-identical in this download
(sha256 `7ba308cc…ae4093`); both are kept so that a reader can check that claim
without trusting this table.

## Not committed (too large for Git; restored by hash)

| File | Bytes | sha256 (prefix) | Source |
|---|---|---|---|
| `training_features.tif` | 418,912,844 | `4371c82e…123bc5` | competition data page (login required), 19-band feature stack at 100 m |
| `external/lidar_scarp_features_u8.tif` | ~36 MB | pinned in `evidence/ingest.json` | official lidar-derived scarps, 12 bands, uint8, same 100 m grid |

Restore them with the official downloader, then verify the hashes against
`evidence/ingest.json` before running anything:

```bash
bash scripts/download_official_data.sh
python scripts/verify_grid.py          # grid + hash verification, writes evidence/
```

A run started without these files fails loudly: `run_lane.py ingest` checks the
lidar hash and the grid before it does any work.
