"""GEMSDOE65 lane: selection-bias-aware PU learning for fault mapping.

This package holds the *only* lane-specific code in this repository.  The
shared, reusable instruments (metric, holdout, emitter, writer, validator,
uniqueness) live in :mod:`gems57` and are imported verbatim from the pinned
sibling template -- they are not forked here.

The lane models the published catalogue as **Selected At Random (SAR)**
conditional on a small, declared set of observables:

    e(x) = P(selected into the catalogue | true fault, x)

estimated with the EM method of

* Bekker & Davis (2018), *Learning from Positive and Unlabeled Data under the
  Selected At Random Assumption*, PMLR v94:8-22,
  https://proceedings.mlr.press/v94/bekker18a.html  (module :mod:`gems65.sarem`)

and used in the propensity-aware empirical risk of

* Bekker, Robberechts & Davis (2019), *Beyond the Selected Completely At Random
  Assumption for Learning from Positive and Unlabeled Data*, ECMLPKDD 2019,
  arXiv:1809.03207  (module :mod:`gems65.risks`)

with the inverse-propensity weights clipped at 10, against an nnPU baseline on
identical spatially blocked folds.
"""

__all__ = ["covariates", "sarem", "risks"]
