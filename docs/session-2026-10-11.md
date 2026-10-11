# Three-pass session review — 2026-10-11 UTC

## Pass 1 — implement what the evidence supports

- Re-read the project brief and inspected the starter checkout. At the start of this lane the tracked tree contained only `README.md`; official competition files, shared evaluator/writer/validator, prior-raster registry, and TIFF were absent.
- Added the standing charter, SAR-aware research design, four ranked hypotheses, source/irregularity registers, submission guide, status notes, and a fail-closed presence-only audit. The site leads with an unambiguous **no approved TIF / do not submit** decision.
- Integrated the shared `docs/` research site and readiness audit from main rather than retaining duplicate root pages, preflight implementation, or a second run card. The single canonical card is `docs/data/run-card.json`.
- No model or TIFF was created, no weekly slot was used, no prior raster was copied, and no score or experiment result was invented.

## Pass 2 — review for bugs, wrong assumptions, and missing requirements

- **Score provenance:** The cited GEMSDOE32 page labels its named H33 artifact “UNSCORED”; the manifest has `receipt: null`. A participant-level public board does not identify uploaded filenames. There is no receipt connecting the H33 file to a score, so the attribution and its cause remain unknown.
- **Competition terms / feed correction:** Review of the [DrivenData Terms of Use](https://www.drivendata.org/termsofuse/) found an explicit prohibition on automated site access for monitoring/copying and on manual monitoring/copying without prior written consent. The merged main baseline had a scheduled leaderboard scraper and mirrored rows. This branch removes the fetch/parser, scheduled trigger, copied rows, rendering code, and associated tests; the site links directly to the official page only. No written permission or authorized API is established. Do not reintroduce a snapshot/feed without authorization.
- **Mapping evidence:** Direct review of Giddens & Faulds (2025), SGP-TR-229, confirms the paper's study-specific statement that about 25% of its study area was mapped in sufficient detail and its warning that steep range-front relief can make step-overs easier to identify. The reported range-front association is also about their identified step-over inventory, not all faults or the competition footprint. The 25% number is not an exhaustive-coverage mask or competition-wide propensity anchor.
- **Map-index scope:** USGS 7.5-minute grid polygons are map frames; NGMDB map records do not prove exhaustive fault coverage. No absolute propensity scale is claimed without a footprint and completeness audit.
- **External gravity scope:** USGS ScienceBase metadata for DOI `10.5066/P13BAFSV` identifies a gravity-derived depth-to-basement raster bundle, CC0, at one-mile node spacing, with a study area predominantly in eastern Nevada/western Utah. No raster was downloaded or tested for exact GeoDAWN overlap, resolution, or alignment.
- **No private evaluator substitution:** The public sibling repository has related block/emission tools, not the required buffered whole-segment hide-and-recover evaluator. They were not copied or substituted.
- **Pages publishing scope:** The Pages API was last observed in legacy `main:/` mode, and the public URL served the previous README page. This branch adds a root redirect as a legacy fallback. The Actions workflow carries a guard and will not deploy the docs artifact unless the repository source is GitHub Actions. This integration could not change repository settings (HTTP 403). Verify the public URL after merge; if Actions publishing is desired, a repository admin must change Settings → Pages → Source. The Arena preview remains available in the meantime.

## Pass 3 — final re-check against the request

- Four ranked, within-lane candidates are documented, with mechanism, observability signature, missing-label explanation, non-fault mimics, cost, and explicit unmeasured status. Global novelty remains unverified; prior sibling work includes SAR/nnPU and PU-proxy variants.
- The top candidate has **not** been validated because data, shared evaluator/writer/validator, and registry are absent. Feature-only leakage canaries, same-fold SAR-vs-nnPU comparison, overall/high-propensity holdout gates, registry rank correlation, 3-pixel overlap, raster validation, and a 95% CI were not run. No `HOLDOUT-DTI` or `ORGANIZER-CONFIRMED` result is claimed.
- Final local checks: the Python unit suite, JSON parsing, static HTML links/fragments, Markdown links, and local site smoke tests passed. The readiness audit correctly reports a blocked/negative gate because prerequisites remain absent. The site contains no TIFF, stored leaderboard rows, or active leaderboard fetch.
- The single canonical run card records null/`NOT RUN` results, no submission name or hash, and a negative verdict. The run card is tested by the suite. The public Pages URL is not yet re-verified after this branch's root redirect; use the working Arena preview until it is.

## Outcome

**Negative, by design.** The requested candidate experiment and unique TIFF cannot be responsibly produced from the files in this checkout; required shared tools and data are absent. The site provides a clear submission block, auditable research registers, direct source links, and a link-only official leaderboard pointer; it does not scrape or mirror the board. Public Pages publication still requires a post-merge check, and the Actions workflow needs the Pages source set to GitHub Actions before it can deploy. No score projection is presented as a result, no credentials or data were invented, and no weekly slot was spent.
