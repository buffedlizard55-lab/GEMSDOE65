# Review status — 2026-10-11 UTC

## Result

**Negative / blocked. No submission candidate was generated, no competition slot was used, and no TIFF is approved for download or submission.** “Negative” means the required improvement evidence and prerequisites are unavailable; it does not mean the proposed SAR-EM method was scientifically falsified.

## Repository and experiment readiness

The original lane checkout had one tracked file (`README.md`) and no pipeline. The current integrated repository adds research documentation, a static site, and a fail-closed presence-only readiness audit. The following remain absent: authorized competition data, cached feature stack, exact shared holdout evaluator, shared submission writer, official validator, prior-raster registry, and any candidate GeoTIFF.

Run the presence-only check with:

```bash
python3 scripts/audit_lane_readiness.py
```

A successful presence audit would still not be a scientific pass, format validation, or permission to submit. The check intentionally fails closed when any required inputs/tool/registry are missing.

## What is available

- The standing project charter and selection-bias-aware SAR/PU research lane are in the [repository README](https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/README.md).
- Four ranked, in-lane hypotheses and an exact next-experiment plan are in [`HYPOTHESES.md`](HYPOTHESES.md) and the [site hypothesis page](hypotheses.html).
- Primary literature, USGS geospatial sources, claim scope, and score provenance are recorded in [`SOURCES.md`](SOURCES.md) and [`RESEARCH.md`](RESEARCH.md).
- The executive summary explains the format and portal steps, but explicitly says not to submit while the gate is closed: [`SUBMISSION_GUIDE.md`](SUBMISSION_GUIDE.md) / [site version](executive-summary.html).
- The machine-readable negative run card is [`data/run-card.json`](data/run-card.json). There is one canonical card; no duplicate evidence card is maintained.

## Leaderboard access and terms

The [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) is linked directly, but its rows are not stored or refreshed on this site. The [DrivenData Terms of Use](https://www.drivendata.org/termsofuse/) page inspected prohibits automated access for monitoring/copying and manual monitoring/copying without prior written consent. A scraper, scheduled fetch, and mirrored rows inherited from the merged baseline were removed. No written permission or authorized API is established; do not restore a feed or snapshot without authorization.

## Remaining limitations

- Authorized competition enrollment/login is needed to obtain the official files; this review did not have access and did not request or store credentials.
- The shared template's cached feature stack, `evaluate_holdout.py`, `submission_writer.py`, validator, and raster registry must be made available through the normal authorized workflow. They are intentionally not recreated here.
- Official external LiDAR, gravity, and map-index sources are identified in [`SOURCES.md`](SOURCES.md), but no study-area rasterization, derived-layer license audit, overlap/resolution test, or alignment check was performed.
- Hardware needs are not assessed: without training data and a runnable model there is no basis to claim CPU/GPU sufficiency.
- The Pages API was last observed in legacy `main:/` mode, and the public URL served the previous README-only page. This branch adds a root redirect as a legacy fallback; the Actions workflow is guarded until the Pages source is switched to GitHub Actions. This integration could not change repository settings (HTTP 403). Verify the public URL after merge; until then, use the Arena preview and do not claim this build is published. If Actions deployment is desired, a repository admin must change **Settings → Pages → Source**.

## Required next action

Make the shared template's authorized data, cached feature stack, evaluator, writer, validator, and registry available in this repository/working environment. Then run the top-ranked candidate under the preregistered protocol. No manual file substitution, private tool reimplementation, copied TIFF, or weekly slot is acceptable before every scientific, uniqueness, and format gate passes.
