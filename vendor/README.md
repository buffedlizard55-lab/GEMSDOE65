# Shared-template reuse

`template58/gems57` is an unmodified snapshot of selected shared modules in
`buffedlizard55-lab/58GEMSDOE`. Immutable Git-blob IDs and full SHA256 hashes for
all files are in `evidence/shared_template_pin.json`. The source revision was
subsequently verified as commit `3ccda56feaca7215e2ceef01d755e0c7b5fd486e`.

These are the shared evaluator, exact/brute-force metric, strict spatial folds,
format validator, TIFF/ZIP writer, uniqueness gate and their dependencies.
Historical helper functions are not new hypotheses in this lane. The fitted
SAR-PU model is in `src/gems65/pu.py`; it never reads prior prediction rasters.

Tests fail if any pinned module changes. Fixes must be made in the shared source
and re-pinned with provenance, rather than applied as a private local fork.
The optional `masked_known` fallback issue is documented in the irregularity
ledger; all folds in this run provide `visible`, so it is not exercised.
