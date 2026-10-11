# Candidate hypotheses, ranked

_expected DTI gain per unit of implementation risk, subject to the hard rule that a hypothesis whose data cannot be fetched in the working environment cannot be validated and therefore cannot be promoted_

Generated from `evidence/hypotheses.json` by `src/gems65_sarprop/site_hypotheses.py`; do not edit by hand.

| Rank | Hypothesis | Expected gain | Cost | Status here |
|---|---|---|---|---|
| 1 | QFaults-B transfer: the organisers' own second inventory as a new-fault prior | high (the only hypothesis that targets the scored inventory directly rather than a physical proxy for it) | medium: one fetch from a documented public service, polyline rasterisation, complement mask, distance transform, then the same gated arm comparison used here | not yet run |
| 2 | Thermal-fluid pathway layer (hot springs, well temperatures, geothermometry) | medium in principle, but measured NEGATIVE below | low: local CSV, kernel density, one blended emission sweep | REJECTED on the blocked holdout |
| 3 | Drainage response: chi (chi) transformation and knickpoint density on the provided detrended-elevation band | medium | high: flow routing over 12.3M cells plus network statistics; needs either pysheds/richdem from PyPI or a hand-rolled D8 | not yet run |
| 4 | Radiometric alteration ratios (K, eTh, eU) over the GeoDAWN survey | medium | low-medium: the survey is already published as a GeoTIFF archive; the work is ratioing, resampling to 100 m and the standard gate | not yet run |
| 5 | Seismicity geometry: depth-banded hypocentre density and focal-mechanism strike | low-medium: the footprint's seismicity is sparse and clustered, so the field is noisy at 100 m | medium: API paging with a footprint envelope query, declustering (Gardner-Knopoff or Reasenberg), then the standard gate | not yet run |

## Measured prior: the organisers' own second inventory is largely absent from the training labels

376 traces have a centroid inside the footprint. Share whose centroid lies beyond each distance from the nearest catalogue pixel:

| Distance | Traces | Share |
|---|---|---|
| > 1 px | 235 | 62.5% |
| > 2 px | 199 | 52.9% |
| > 3 px | 168 | 44.7% |
| > 5 px | 122 | 32.4% |
| > 10 px | 72 | 19.1% |

A centroid is a summary point of a clipped trace, so this is an upper bound.

## The locally runnable candidate was rejected

| Blend weight lambda | Dots | HOLDOUT-DTI | TP_w |
|---|---|---|---|
| 0.0 | 72,218 | 0.072048 | 1708 |
| 0.25 | 72,395 | 0.071053 | 1687 |
| 0.5 | 72,498 | 0.069619 | 1654 |
| 1.0 | 72,930 | 0.067694 | 1614 |

Decision: **not supported** (baseline lambda = 0 at 0.072048). The layer is not promoted and no submission slot is spent on it.

## Full register

### #1 — QFaults-B transfer: the organisers' own second inventory as a new-fault prior

- **Layers:** USGS Quaternary Fault and Fold Database polylines (attributes SLIPRT2023, REC2023, SLIPSENSE, MAPSCALE, FTYPE) minus the pixels already covered by the training catalogue; features = distance to the nearest uncovered trace, recency-weighted and slip-rate-weighted
- **Physical signature:** An independent, seismic-hazard-grade compilation of Quaternary surface rupture. Traces present in QFaults but absent from the training catalogue are, by definition, fault geometry the organiser's own label source contains and the training labels do not.
- **Why it catches a fault missing from the catalogue:** The rules state the scored labels come from the USGS Quaternary Fault and Fold Database plus expert-identified new faults, while the training labels came from the INGENIOUS Great Basin compilation. Any QFault trace outside the training catalogue is therefore a direct member of the scored population rather than a proxy for it -- the strongest available prior on the final-round reward.
- **Difference from this repo family:** Sibling lanes rasterised the QFaults service only as a cross-catalogue transfer surrogate (fetch_qfaults.py) and used it to audit proxy-catalogue policy, not as a feature in a submission model. No lane restricted it to the complement of the training catalogue, and none weighted it by REC2023/SLIPRT2023.
- **Expected DTI gain:** high (the only hypothesis that targets the scored inventory directly rather than a physical proxy for it)
- **Implementation cost:** medium: one fetch from a documented public service, polyline rasterisation, complement mask, distance transform, then the same gated arm comparison used here
- **External source:** USGS Quaternary Fault and Fold Database of the United States (2020 release) https://doi.org/10.5066/P9BCVRCK
- **Obtainable?** VERIFIED OBTAINABLE — a sibling lane's fetch_qfaults.py records the live response (14,482 features intersecting the footprint envelope, queried 2026-09-18, service currentVersion 11.5) and the downloaded attribute table (23,386 rows: NAME, SLIPRT2023, REC2023, SLIPSENSE, MAPSCALE, FTYPE_) is present in a sibling checkout. NOT re-fetched in this sandbox: outbound access here is limited to GitHub and PyPI, so the service host is unreachable from this environment.
- **Validated here?** Not runnable in this sandbox (no route to the USGS service). Its prior was measured instead, from the clipped trace table already on disk.

### #2 — Thermal-fluid pathway layer (hot springs, well temperatures, geothermometry)

- **Layers:** GDR 'Well and Spring Temperature and Chemistry' table: measured temperature, quartz/chalcedony/cat geothermometer temperatures, thermal class, at 12,570 distinct grid cells; kernel density at a ~400 m scale
- **Physical signature:** Fluid upflow and discharge. In the Basin and Range, hot springs sit on fault intersections and relay zones, so hot-site density is a map of permeable structure rather than of topography.
- **Why it catches a fault missing from the catalogue:** Surface-rupture mapping requires a scarp; fluid pathways do not. Springs mark blind, buried and small-displacement structures that a surface-rupture catalogue under-maps, which is the same population the organisers' expert round adds.
- **Difference from this repo family:** No lane in this family carries the spring/well temperature table as a model feature; it appears only as background knowledge in a research note.
- **Expected DTI gain:** medium in principle, but measured NEGATIVE below
- **Implementation cost:** low: local CSV, kernel density, one blended emission sweep
- **External source:** GDR geothermal well and spring temperature/chemistry compilation https://gdr.openei.org/submissions/1391
- **Obtainable?** already downloaded in a sibling checkout (27,092 rows, 12,570 distinct grid cells)
- **Validated here?** REJECTED on the blocked holdout at the emission level: every blend weight above zero lowers HOLDOUT-DTI. See evidence/hypothesis_thermal_pathway.json.

### #3 — Drainage response: chi (chi) transformation and knickpoint density on the provided detrended-elevation band

- **Layers:** detrended elevation (official band 6) and its slope (band 7), plus the competition lidar scarps for valley identification; optional 3DEP 1/3 arc-second DEM as a coarse anchor
- **Physical signature:** A channel crossing an active or recently active fault steps down; along-stream chi plots show a break, and knickpoint density anomalies trace the structure responsible even where no scarp was mapped.
- **Why it catches a fault missing from the catalogue:** Fluvial networks integrate vertical motion over 10^4-10^5 yr, so they respond to structures that have insufficient surface expression to be mapped as a scarp but are nonetheless deforming the landscape.
- **Difference from this repo family:** Sibling lanes used elevation edges, curvature, Euler depth, tensor/strain and scarp morphology; none computed a stream network relative metric (chi, ksn, knickpoint density), which is a different observable from gradient products.
- **Expected DTI gain:** medium
- **Implementation cost:** high: flow routing over 12.3M cells plus network statistics; needs either pysheds/richdem from PyPI or a hand-rolled D8
- **External source:** USGS 3DEP (only if a coarse anchor is wanted) https://apps.nationalmap.gov/downloader/
- **Obtainable?** the organisers ship a 1 m DEM link list; the 100 m detrended elevation band is already local, so this hypothesis needs no new download to start
- **Validated here?** queued; not run in this session

### #4 — Radiometric alteration ratios (K, eTh, eU) over the GeoDAWN survey

- **Layers:** GeoDAWN airborne radiometrics: potassium, equivalent thorium and uranium channels, as ratios (K/eTh, eU/eTh) and as a K-enrichment anomaly
- **Physical signature:** Hydrothermal alteration: K metasomatism along fluid pathways, potassic clay alteration, and uranium enrichment in fracture damage zones produce a distinctive K-high / Th-low ratio.
- **Why it catches a fault missing from the catalogue:** Alteration halos record where fluids moved in the past, which persists after the topographic scarp has been erased or buried -- so it can mark the location of a structure with no modern surface expression.
- **Difference from this repo family:** One sibling lane used a radiometric edge-coherence diagnostic; no lane has used the K/Th/U ratio (alteration index) as a model feature.
- **Expected DTI gain:** medium
- **Implementation cost:** low-medium: the survey is already published as a GeoTIFF archive; the work is ratioing, resampling to 100 m and the standard gate
- **External source:** GeoDAWN airborne magnetic and radiometric surveys, northwestern Great Basin (Glen & Earney, 2024) https://doi.org/10.5066/P93LGLVQ
- **Obtainable?** VERIFIED OBTAINABLE — the official 19-band feature stack already carries five bands derived from this survey, and a sibling lane shipped a radiometric-derived diagnostic raster, so the archive has been downloaded successfully in this family before
- **Validated here?** queued; needs the radiometric bands

### #5 — Seismicity geometry: depth-banded hypocentre density and focal-mechanism strike

- **Layers:** ANSS Comprehensive Catalog hypocentres (depth, magnitude) and focal mechanism solutions, projected to the grid; the official band 19 carries only 2-D earthquake density
- **Physical signature:** Active structures concentrate seismicity on planes. A depth band (3-10 km) isolates crustal faults from quarry blasts and deep events, and mechanism nodal planes give the strike to correlate.
- **Why it catches a fault missing from the catalogue:** Seismicity locates active structures regardless of surface expression, so a lineament defined by hypocentres is evidence of a fault the surface catalogue does not contain.
- **Difference from this repo family:** The family used the provided 2-D density band; no lane has used depths, magnitudes or mechanisms to build a 3-D/structural feature.
- **Expected DTI gain:** low-medium: the footprint's seismicity is sparse and clustered, so the field is noisy at 100 m
- **Implementation cost:** medium: API paging with a footprint envelope query, declustering (Gardner-Knopoff or Reasenberg), then the standard gate
- **External source:** ANSS Comprehensive Earthquake Catalog (ComCat) web service https://earthquake.usgs.gov/fdsnws/event/1/
- **Obtainable?** documented public service, no key; not re-verified from this sandbox because outbound access here is limited to GitHub and PyPI. The organisers already ship a 2-D density product derived from the same network, which is independent evidence that the catalogue is obtainable
- **Validated here?** queued; not run in this session

## Next action

Fetch QFaults polylines, rasterise, subtract the training catalogue, and run the same gated arm comparison on the blocked holdout. Promote only if it beats the current arm on the identical draw, and only after the multi-seed repeat.
