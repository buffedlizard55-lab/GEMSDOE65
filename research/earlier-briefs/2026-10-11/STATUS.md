# Status — 2026-10-11T22:16:04Z

**Verdict: negative (tie).** A unique, fully validated candidate GeoTIFF exists and is downloadable,
but the registered promotion gate did not pass, so it is a **research artifact — do not submit**.

* E1 (registered instrument, uniform withholding, 16 cells): SAR 0.023628
  vs nnPU 0.023671; paired Δ = −4.3e−05, 95 % CI [−3.9e−04, +3.2e−04].
* E2 (bias-matched withholding, 8 cells): SAR 0.020985 vs nnPU
  0.020816; Δ = +1.70e−04, 95 % CI [−9.3e−05, +4.1e−04].
* Leakage canaries: max single-feature AUC 0.623 (E1),
  0.668 (E2).
* Registry: 62 priors, worst |ρ| 0.0366, no hash
  match, worst forward overlap 0.9975 against a saturated lattice
  witness (control: random field 0.9987).
* Candidate: `gems65-sarprop-em-v2-20261011-9b1c65d-zeros.tif`, sha256 `5aee83cb2e55f0122432611ff46af6fdd1e5a9182f263888e03f667647315c37`,
  28,047 dots, every validator check passed.
