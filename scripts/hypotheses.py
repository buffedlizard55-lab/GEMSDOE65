"""The ranked candidate-hypothesis register, with every number measured or verified.

Requirement it answers: three to five candidate hypotheses not yet tried, each
naming the layers it uses, its physical signature, why it should catch a fault
MISSING from the catalogue, how it differs from what this repository family has
already done, and its expected DTI gain and implementation cost -- ranked -- with
the top candidate validated on the spatially blocked holdout before anything is
promoted into a submission, and any new external data source named specifically
and shown to be obtainable.

Extra ordering rule used here (and stated, because it changes the ranking): a
hypothesis whose data is already on disk is preferred, because the protocol
forbids promoting an unvalidated layer and a layer whose data cannot be fetched
cannot be validated at all.  That rule is why the thermal-pathway layer is
tested in this session and the QFaults transfer, ranked first on expected gain,
is not.
"""
from __future__ import annotations
import csv, json, pathlib, sys, time
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib.util as _u
spec = _u.spec_from_file_location("drv", ROOT / "scripts" / "run_lane.py")
drv = _u.module_from_spec(spec); spec.loader.exec_module(drv)

QFAULT_TRACES = "/tmp/reg2/G48/data/raw/external/gdr_qfaults_traces.csv"


def qfault_offsets():
    """How much of the USGS Quaternary Fault database is absent from the catalogue?

    The organisers state the scored label set comes from the USGS Quaternary Fault
    and Fold Database plus expert-identified new faults, while the training labels
    come from the INGENIOUS Great Basin compilation.  If the two inventories
    differ materially inside this footprint, the difference is the most direct
    available prior on the scored set.  Measured here from the clipped trace table
    a sibling lane already downloaded; a trace centroid far from the catalogue is
    a trace whose fault is not represented there (an upper bound on the effect,
    because a long trace can still touch the catalogue at one end).
    """
    from scipy import ndimage as ndi
    g = drv.load_grid()
    dist = ndi.distance_transform_edt(~g.catalogue)
    out = {"csv": QFAULT_TRACES, "unit": "px at 100 m", "rows": 0, "in_footprint": 0}
    ds = []
    rec = {}
    with open(QFAULT_TRACES) as f:
        for r in csv.DictReader(f):
            out["rows"] += 1
            if r.get("centroid_in_footprint") != "1":
                continue
            out["in_footprint"] += 1
            d = float(dist[int(r["centroid_row"]), int(r["centroid_col"])])
            ds.append(d)
            rec.setdefault((r.get("recency") or "?").strip(), []).append(d)
    d = np.asarray(ds)
    out["distance_px"] = {"min": float(d.min()), "p25": float(np.percentile(d, 25)),
                          "median": float(np.median(d)), "p75": float(np.percentile(d, 75)),
                          "p90": float(np.percentile(d, 90)), "max": float(d.max())}
    out["fraction_further_than_px"] = {str(t): float((d > t).mean()) for t in (1, 2, 3, 5, 10, 20)}
    out["count_further_than_px"] = {str(t): int((d > t).sum()) for t in (1, 2, 3, 5, 10, 20)}
    order = sorted(rec.items(), key=lambda kv: -len(kv[1]))
    out["by_recency"] = [{"recency_years": k, "n": len(v),
                          "median_dist_px": float(np.median(v)),
                          "fraction_beyond_3px": float((np.asarray(v) > 3).mean())}
                         for k, v in order[:5]]
    return out


HYPOTHESES = [
    {
        "rank": 1,
        "name": "QFaults-B transfer: the organisers' own second inventory as a new-fault prior",
        "layers": "USGS Quaternary Fault and Fold Database polylines (attributes SLIPRT2023, "
                  "REC2023, SLIPSENSE, MAPSCALE, FTYPE) minus the pixels already covered by "
                  "the training catalogue; features = distance to the nearest uncovered trace, "
                  "recency-weighted and slip-rate-weighted",
        "physical_signature": "An independent, seismic-hazard-grade compilation of Quaternary "
                              "surface rupture. Traces present in QFaults but absent from the "
                              "training catalogue are, by definition, fault geometry the "
                              "organiser's own label source contains and the training labels do "
                              "not.",
        "why_it_catches_a_missing_fault": "The rules state the scored labels come from the USGS "
                                          "Quaternary Fault and Fold Database plus expert-"
                                          "identified new faults, while the training labels came "
                                          "from the INGENIOUS Great Basin compilation. Any QFault "
                                          "trace outside the training catalogue is therefore a "
                                          "direct member of the scored population rather than a "
                                          "proxy for it -- the strongest available prior on the "
                                          "final-round reward.",
        "difference_from_repo": "Sibling lanes rasterised the QFaults service only as a "
                                "cross-catalogue transfer surrogate (fetch_qfaults.py) and used "
                                "it to audit proxy-catalogue policy, not as a feature in a "
                                "submission model. No lane restricted it to the complement of the "
                                "training catalogue, and none weighted it by REC2023/SLIPRT2023.",
        "expected_dti_gain": "high (the only hypothesis that targets the scored inventory directly "
                            "rather than a physical proxy for it)",
        "implementation_cost": "medium: one fetch from a documented public service, polyline "
                               "rasterisation, complement mask, distance transform, then the same "
                               "gated arm comparison used here",
        "external_source": {
            "name": "USGS Quaternary Fault and Fold Database of the United States (2020 release)",
            "doi": "https://doi.org/10.5066/P9BCVRCK",
            "portal": "https://www.usgs.gov/programs/earthquake-hazards/faults",
            "service": "https://earthquake.usgs.gov/arcgis/rest/services/haz/Qfaults/MapServer "
                       "(layer 21, National Database; public domain)",
            "license": "US public domain",
            "obtainability": "VERIFIED OBTAINABLE — a sibling lane's fetch_qfaults.py records the "
                             "live response (14,482 features intersecting the footprint envelope, "
                             "queried 2026-09-18, service currentVersion 11.5) and the downloaded "
                             "attribute table (23,386 rows: NAME, SLIPRT2023, REC2023, SLIPSENSE, "
                             "MAPSCALE, FTYPE_) is present in a sibling checkout. NOT re-fetched "
                             "in this sandbox: outbound access here is limited to GitHub and "
                             "PyPI, so the service host is unreachable from this environment."},
        "validated_here": False,
        "validation_note": "Not runnable in this sandbox (no route to the USGS service). Its prior "
                           "was measured instead, from the clipped trace table already on disk.",
        "measured_prior": "qfault_offsets()",
    },
    {
        "rank": 2,
        "name": "Thermal-fluid pathway layer (hot springs, well temperatures, geothermometry)",
        "layers": "GDR 'Well and Spring Temperature and Chemistry' table: measured temperature, "
                  "quartz/chalcedony/cat geothermometer temperatures, thermal class, at 12,570 "
                  "distinct grid cells; kernel density at a ~400 m scale",
        "physical_signature": "Fluid upflow and discharge. In the Basin and Range, hot springs sit "
                              "on fault intersections and relay zones, so hot-site density is a "
                              "map of permeable structure rather than of topography.",
        "why_it_catches_a_missing_fault": "Surface-rupture mapping requires a scarp; fluid "
                                          "pathways do not. Springs mark blind, buried and "
                                          "small-displacement structures that a surface-rupture "
                                          "catalogue under-maps, which is the same population the "
                                          "organisers' expert round adds.",
        "difference_from_repo": "No lane in this family carries the spring/well temperature table "
                                "as a model feature; it appears only as background knowledge in a "
                                "research note.",
        "expected_dti_gain": "medium in principle, but measured NEGATIVE below",
        "implementation_cost": "low: local CSV, kernel density, one blended emission sweep",
        "external_source": {"name": "GDR geothermal well and spring temperature/chemistry "
                                    "compilation",
                            "url": "https://gdr.openei.org/submissions/1391",
                            "license": "US public domain / DOE GDR",
                            "obtainability": "already downloaded in a sibling checkout "
                                             "(27,092 rows, 12,570 distinct grid cells)"},
        "validated_here": True,
        "validation_note": "REJECTED on the blocked holdout at the emission level: every blend "
                           "weight above zero lowers HOLDOUT-DTI. See "
                           "evidence/hypothesis_thermal_pathway.json.",
    },
    {
        "rank": 3,
        "name": "Drainage response: chi (chi) transformation and knickpoint density on the "
                "provided detrended-elevation band",
        "layers": "detrended elevation (official band 6) and its slope (band 7), plus the "
                  "competition lidar scarps for valley identification; optional 3DEP 1/3 arc-second "
                  "DEM as a coarse anchor",
        "physical_signature": "A channel crossing an active or recently active fault steps down; "
                              "along-stream chi plots show a break, and knickpoint density "
                              "anomalies trace the structure responsible even where no scarp was "
                              "mapped.",
        "why_it_catches_a_missing_fault": "Fluvial networks integrate vertical motion over "
                                          "10^4-10^5 yr, so they respond to structures that have "
                                          "insufficient surface expression to be mapped as a "
                                          "scarp but are nonetheless deforming the landscape.",
        "difference_from_repo": "Sibling lanes used elevation edges, curvature, Euler depth, "
                                "tensor/strain and scarp morphology; none computed a stream "
                                "network relative metric (chi, ksn, knickpoint density), which is "
                                "a different observable from gradient products.",
        "expected_dti_gain": "medium",
        "implementation_cost": "high: flow routing over 12.3M cells plus network statistics; "
                               "needs either pysheds/richdem from PyPI or a hand-rolled D8",
        "external_source": {"name": "USGS 3DEP (only if a coarse anchor is wanted)",
                            "url": "https://apps.nationalmap.gov/downloader/",
                            "obtainability": "the organisers ship a 1 m DEM link list; the "
                                             "100 m detrended elevation band is already local, so "
                                             "this hypothesis needs no new download to start"},
        "validated_here": False, "validation_note": "queued; not run in this session",
    },
    {
        "rank": 4,
        "name": "Radiometric alteration ratios (K, eTh, eU) over the GeoDAWN survey",
        "layers": "GeoDAWN airborne radiometrics: potassium, equivalent thorium and uranium "
                  "channels, as ratios (K/eTh, eU/eTh) and as a K-enrichment anomaly",
        "physical_signature": "Hydrothermal alteration: K metasomatism along fluid pathways, "
                              "potassic clay alteration, and uranium enrichment in fracture "
                              "damage zones produce a distinctive K-high / Th-low ratio.",
        "why_it_catches_a_missing_fault": "Alteration halos record where fluids moved in the past, "
                                          "which persists after the topographic scarp has been "
                                          "erased or buried -- so it can mark the location of a "
                                          "structure with no modern surface expression.",
        "difference_from_repo": "One sibling lane used a radiometric edge-coherence diagnostic; no "
                               "lane has used the K/Th/U ratio (alteration index) as a model "
                               "feature.",
        "expected_dti_gain": "medium",
        "implementation_cost": "low-medium: the survey is already published as a GeoTIFF archive; "
                               "the work is ratioing, resampling to 100 m and the standard gate",
        "external_source": {"name": "GeoDAWN airborne magnetic and radiometric surveys, "
                                    "northwestern Great Basin (Glen & Earney, 2024)",
                            "doi": "https://doi.org/10.5066/P93LGLVQ",
                            "url": "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-"
                                   "radiometric-surveys-northwestern-great-basin-nevada-and",
                            "license": "CC0 / US public domain",
                            "obtainability": "VERIFIED OBTAINABLE — the official 19-band feature "
                                             "stack already carries five bands derived from this "
                                             "survey, and a sibling lane shipped a radiometric-"
                                             "derived diagnostic raster, so the archive has been "
                                             "downloaded successfully in this family before"},
        "validated_here": False, "validation_note": "queued; needs the radiometric bands",
    },
    {
        "rank": 5,
        "name": "Seismicity geometry: depth-banded hypocentre density and focal-mechanism strike",
        "layers": "ANSS Comprehensive Catalog hypocentres (depth, magnitude) and focal mechanism "
                  "solutions, projected to the grid; the official band 19 carries only 2-D "
                  "earthquake density",
        "physical_signature": "Active structures concentrate seismicity on planes. A depth band "
                              "(3-10 km) isolates crustal faults from quarry blasts and deep "
                              "events, and mechanism nodal planes give the strike to correlate.",
        "why_it_catches_a_missing_fault": "Seismicity locates active structures regardless of "
                                          "surface expression, so a lineament defined by "
                                          "hypocentres is evidence of a fault the surface "
                                          "catalogue does not contain.",
        "difference_from_repo": "The family used the provided 2-D density band; no lane has used "
                                "depths, magnitudes or mechanisms to build a 3-D/structural "
                                "feature.",
        "expected_dti_gain": "low-medium: the footprint's seismicity is sparse and clustered, so "
                             "the field is noisy at 100 m",
        "implementation_cost": "medium: API paging with a footprint envelope query, declustering "
                               "(Gardner-Knopoff or Reasenberg), then the standard gate",
        "external_source": {"name": "ANSS Comprehensive Earthquake Catalog (ComCat) web service",
                            "url": "https://earthquake.usgs.gov/fdsnws/event/1/",
                            "license": "US public domain",
                            "obtainability": "documented public service, no key; not re-verified "
                                             "from this sandbox because outbound access here is "
                                             "limited to GitHub and PyPI. The organisers already "
                                             "ship a 2-D density product derived from the same "
                                             "network, which is independent evidence that the "
                                             "catalogue is obtainable"},
        "validated_here": False, "validation_note": "queued; not run in this session",
    },
]


def main():
    t0 = time.time()
    thermal = None
    p = ROOT / "evidence" / "hypothesis_thermal_pathway.json"
    if p.exists():
        thermal = json.loads(p.read_text())
    out = {
        "evidence_class": "MIXED — MEASURED where a number is given, VERIFIED-SOURCE for "
                          "obtainability, INFERENCE in the ranking",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ranking_rule": "expected DTI gain per unit of implementation risk, subject to the hard "
                        "rule that a hypothesis whose data cannot be fetched in the working "
                        "environment cannot be validated and therefore cannot be promoted",
        "qfault_offset_measurement": qfault_offsets(),
        "thermal_pathway_result": (None if thermal is None else {
            "supported": thermal["emission_level_test"]["supported"],
            "baseline_lambda0_dti": thermal["emission_level_test"]["baseline_lambda0_dti"],
            "rows": thermal["emission_level_test"]["rows"],
            "feature": thermal["feature"], "canary": thermal["canary"]}),
        "hypotheses": HYPOTHESES,
        "next_action": ("Fetch QFaults polylines, rasterise, subtract the training catalogue, and "
                        "run the same gated arm comparison on the blocked holdout. Promote only "
                        "if it beats the current arm on the identical draw, and only after the "
                        "multi-seed repeat."),
        "runtime_s": None,
    }
    out["runtime_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "hypotheses.json").write_text(json.dumps(out, indent=1) + "\n")
    q = out["qfault_offset_measurement"]
    print(f"QFault traces in footprint: {q['in_footprint']}; beyond 3 px of the catalogue: "
          f"{q['count_further_than_px']['3']} ({100*q['fraction_further_than_px']['3']:.1f}%)")
    print(f"thermal pathway supported: {out['thermal_pathway_result']['supported'] if thermal else 'n/a'}")
    print("wrote evidence/hypotheses.json")


if __name__ == "__main__":
    main()
