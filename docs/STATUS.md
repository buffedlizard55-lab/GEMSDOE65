# Review status — 2026-10-11 UTC

## Result

**Negative / blocked. No submission candidate was generated and no competition slot was used.** “Negative” here means the required improvement evidence is unavailable, not that the proposed SAR-EM method was scientifically falsified.

## Repository inspection

The original checkout had one tracked file (`README.md`) and no pipeline. The following are absent: official competition data, cached feature stack, data preparation/downloader scripts, shared holdout evaluator, shared submission writer, official validator, prior-raster registry, and any candidate GeoTIFF. The official DrivenData data page returned a login page in this session.

## What this change adds

- A standing project charter and evidence/source register.
- A clear static-site landing page and Executive Summary with explicit “do not submit” state.
- Four ranked, in-lane SAR propensity hypotheses and an exact next-experiment plan.
- A fail-closed path inventory, plus standard-library tests. It does not build private versions of the required shared evaluation/writer/validator tools.
- A machine-readable negative run card; unknown results are null/NOT RUN.

## Access and remaining limitations

- Authorized DrivenData competition enrollment/login is needed to obtain the official files; this session did not have access and did not request or store credentials.
- The shared template's cached feature stack, `evaluate_holdout.py`, `submission_writer.py`, validator, and registry must be made available through the normal authorized project workflow. They are intentionally not recreated here.
- Official external LiDAR/gravity/map-index sources are identified in `docs/SOURCES.md`, but no study-area rasterization, license audit for a derived layer, or alignment check was performed.
- Hardware needs are not assessed: without training data and a runnable model there is no basis to claim CPU/GPU sufficiency.
- The site links to the live official leaderboard and stores a dated review snapshot; an automated “current feed” is not implemented. Do not add scheduled scraping until the competition's rules and access terms are checked.
- GitHub API reports a public legacy Pages site sourced from `main:/`. The new pages are not yet confirmed live; verify the published site after the PR merges.

## Required next action

Make the shared template's authenticated data, cached feature stack, evaluator, writer, validator, and registry available in this repository/working environment through the authorized project workflow. Then run the top-ranked candidate using the preregistered protocol. No manual file substitution or copied TIFF is acceptable.
