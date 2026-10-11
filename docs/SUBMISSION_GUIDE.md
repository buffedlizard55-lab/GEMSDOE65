# Executive summary: how to submit a GEMS GeoTIFF

## Is there a file to download from this repository now?

**No. It is NOT OK to download or submit a file from this repository.** There is no candidate TIFF, no official sample grid, no validator output, and no holdout/uniqueness gate result. Do not use a sibling site's TIFF or an arbitrary placeholder. The landing page deliberately has no active download button.

## What the competition expects

The official problem page says the upload is a prediction raster for faults across the region. The raster must be a **single-band float32 GeoTIFF** on the official training/sample grid: EPSG:32611, 100 m, same bounds/shape/geotransform, predictions in [0,1], and null/NaN outside the region footprint. The official metric is distance-weighted Tversky with alpha 0.2, beta 0.8, and a 300 m triangular kernel. See [official problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).

## Submission workflow after a candidate actually passes

1. Open this project's Executive Summary and check the prominent status. Download only if it says **OK TO SUBMIT**, links exactly one named artifact, records its SHA-256, and points to a passing validator and run card.
2. Download the linked `.tif` (or a ZIP containing exactly one `.tif`, if the competition portal requires that packaging). Never upload a file from an archive/quarantine or an older candidate.
3. Sign in to the [DrivenData competition](https://www.drivendata.org/competitions/306/competition-doe-gems/) and open **New submission**.
4. Choose the downloaded single-band GeoTIFF in **File to submit**.
5. Enter the short note shown beside the artifact's unique submission name. Keep it within the contest form's limit and record the portal receipt immediately after submission.
6. Confirm the portal accepted the same artifact and that the receipt identifies the file. Record its score as `ORGANIZER-CONFIRMED` only by copying it from that receipt. Do not confuse a local projection, public leaderboard row, or holdout score with the receipt.

No submission slot is used by this repository, and this guide does not submit anything on the user's behalf.

## Preventing “Predicted values must be in range [0, 1]”

The required check is a raster check, not a promise in documentation. Once a real candidate and sample grid are available, validate the written bytes after normalization:

- one band and float32;
- CRS, shape, transform, resolution, and bounds equal the official sample grid;
- every in-footprint value is finite and in [0,1];
- no NaN is present inside the footprint;
- outside-footprint cells are null/NaN only;
- the shared competition validator succeeds, and a separate read-back confirms the written raster.

Do not replace outside-footprint NaNs with zero unless the official sample/competition validator explicitly requires it. The task prompt requires NaN only outside the footprint. If probability normalization is needed, apply it only to valid in-footprint cells, handle constant arrays explicitly, then re-check the final file. These steps have **not** been run because no raster or validator exists here.

## Current blocker

The official [data page](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) redirected this review to login. The current repository also lacks the template's cached stack, `evaluate_holdout.py`, `submission_writer.py`, and validator. See `python scripts/preflight.py` and [`IRREGULARITIES.md`](IRREGULARITIES.md). No fake file is offered in place of those prerequisites.
