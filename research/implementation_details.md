# Executed configuration (recorded after the run, not retroactive preregistration)

- Three reference-propensity scenarios: primary 0.50, sensitivities 0.25 and 0.75.
- Four shared spatial folds; 80-pixel (8 km) training exclusion, including whole-component tails.
- Training sample per fold: up to 6,000 labeled positives and 30,000 catalogue-complement pixels, without replacement. Population-correcting weights make these a marginal-population expectation, not a balanced empirical prevalence.
- Sampler seeds: 651100–651103; identical samples/designs across scenarios and comparator.
- Twelve physical covariates; outcome basis: intercept, clipped robust-standardized covariates, and one-quarter squares (25 coefficients). Propensity basis: first five covariates only, with a fixed assumed intercept.
- EM initialization: constant class probability observed-positive fraction / reference propensity; propensity slopes initially zero.
- EM E-step: exact posterior with no local-certainty decay (d=1).
- Fixed 25-iteration EM cap; convergence requires at least five iterations and population-weighted mean absolute propensity change below 1e-4. This **did not occur** in any fold/scenario.
- M-step and risk optimization: SciPy L-BFGS-B, fixed L2 1e-4, coefficient bounds [-20,20], maximum 150 inner iterations, ftol 1e-10, gtol 1e-6. Inner optimizers succeeded.
- Final signed-risk target: s * min(1/e,10). nnPU prior is the same sample's population-weighted corrected positive mass. nnPU minimizes the nonnegative-risk objective directly; it does not implement the stochastic reverse-gradient training schedule.
- Inference: sigmoid confidence in [0,1], float32; no min–max stretch of the TIFF. Only the illustrative PNG is contrast-stretched.
- Pooled block bootstrap: 1,000 draws, seed 651011, 20 km cells, same block draws for both arms, integer truth-count equality checked.
- Original pre-fit canary: each of the twelve physical covariates in each fold. Pass-2 audit: 144 raw/standardized/quadratic checks with identical training samples, no refitting. Future runner now performs all of them before training.

The preregistration prose fixed the mechanism/scenarios/folds/gates but did not spell out all numeric solver/sample settings. These were fixed in execution code before fitting, not tuned after seeing results. `evidence/execution_provenance.json` records the original runner/model hashes before the pass-2 safety edits. A future experiment should preregister a complete machine-readable configuration and enough iteration budget to establish convergence. These finite-iteration measurements must not be represented as converged SAR propensity estimates.
