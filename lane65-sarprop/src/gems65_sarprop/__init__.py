"""GEMSDOE65 -- selection-bias-aware transcriptionally-grounded PU fault placement.

Package layout
--------------
    grid        official grid constants, footprint pins, raster I/O
    features    the 19 official bands and the 5 propensity covariates
    propensity  SAR-EM (Bekker & Davis, PMLR v94 2018)
    pu          propensity-aware empirical risk (arXiv:1809.03207) + nnPU
    metric      the official distance-weighted Tversky index, exactly
    lane        sampling, fitting, whole-grid scoring, emission helpers
    template/   the shared tools, vendored VERBATIM (see template/PROVENANCE.md)
"""

__version__ = "0.1.0"
