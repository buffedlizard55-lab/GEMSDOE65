# Executive summary: how to submit a GEMS GeoTIFF

## Is there a file to download from this repository now?

**No. It is NOT OK to download or submit a file from this repository.** There is no candidate TIFF, no official sample grid, no validator output, and no holdout/uniqueness gate result. Do not use a sibling site's TIFF or an arbitrary placeholder. The landing page deliberately has no active download button. The canonical negative run card is [`data/run-card.json`](data/run-card.json).

## What the competition expects

The official problem page describes a prediction raster for faults across the region. The raster must be a **single-band float32 GeoTIFF** on the official training/sample grid: EPSG:32611, 100 m, same bounds/shape/geotransform, predictions in `[0,1]`, and null/NaN outside the region footprint. The official metric is distance-weighted Tversky with alpha 0.2, beta 0.8, and a 300 m triangular kernel. See the [official problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).

The exact dimensions, transform, CRS, and footprint mask must be read from the authenticated official template. Do not infer them from a similar raster or another repository.

## Submission workflow after a candidate actually passes

1. Open the project's status page and run card. Proceed only if the site presents an explicit **Cleared to submit** state and a unique download button for the candidate recorded by that run card. A research note, projected score, old file, or format-only check is not promotion.
2. Confirm the exact shared evaluator version, withheld-positive count, paired HOLDOUT-DTI and 95% CI, registry correlation and dot overlap, raster SHA-256, and passing validator results are recorded. The candidate must beat both the current holdout best and matched nnPU baseline overall, and not lose in the highest-propensity tercile. If the current best is unavailable, do not promote.
3. Confirm the holdout used whole fault segments with a buffer; catalogue-based features were derived from visible faults only; visible fault pixels were masked exactly; feature-only leakage canaries passed; and the comparison used identical folds. No weekly slot may be used before these scientific and uniqueness gates pass.
4. Download only the approved `.tif` (or a ZIP containing exactly one `.tif` if the portal requires that packaging). Never rename or repackage an old file to make it appear unique. Preserve the SHA-256 and the short note shown for the exact run.
5. Sign in to the [DrivenData DOE GEMS competition](https://www.drivendata.org/competitions/306/competition-doe-gems/) using the authorized account and open the [submissions page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/). Choose **New submission**.
6. Under **File to submit**, choose the approved TIFF. In **Note (optional)**, paste the short unique note associated with the same run, keeping it under 140 characters for this project.
7. Before submitting, verify the filename, note, checksum, and green project gate all describe the same candidate. If the form reports “Predicted values must be in range [0, 1]”, stop and report the error. Do not clip a different file and re-upload it without rerunning validation.
8. Submit only after all checks pass. Save the organizer's submission-page receipt and score record. Attribute a score to the file only when that receipt identifies the exact submission.

No submission slot is used by this repository, and this guide does not submit anything on the user's behalf.

## Preventing “Predicted values must be in range [0, 1]”

The required check is on the actual written raster bytes, not a promise in documentation. Once real data, a candidate, and the official sample grid are available, validate the final file after normalization:

- exactly one band and float32;
- CRS, shape, transform, resolution, and bounds equal the official sample grid;
- every in-footprint value is finite and in `[0,1]`;
- no NaN is present inside the footprint;
- outside-footprint cells are null/NaN only;
- the shared competition validator succeeds, and a separate read-back confirms the written raster.

Do not replace outside-footprint NaNs with zero unless the official sample/validator explicitly requires it. If probability normalization is required, apply it only to valid in-footprint cells, handle constant arrays explicitly, then re-check the final file. These steps have **not** been run because no raster or validator exists here.

## Current blocker

The official [data page](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) returned the login page in this unauthenticated review. The repository also lacks the shared cached stack, `evaluate_holdout.py`, `submission_writer.py`, validator, and prior-raster registry. Use `python3 scripts/audit_lane_readiness.py` for a presence-only inventory; a passing inventory is not a scientific pass or TIF authorization. See [`IRREGULARITIES.md`](IRREGULARITIES.md). No fake file is offered in place of the missing prerequisites.
