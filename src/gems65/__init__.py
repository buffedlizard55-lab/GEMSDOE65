"""GEMSDOE65 -- selection-bias-aware PU learning lane (SAR propensity).

Lane (verbatim from the parallel-run protocol assigned to this session):

    Treat the catalogue as positives selected at random given covariates (SAR),
    not completely at random.  Estimate the propensity e(x) = P(labeled | fault, x)
    with the EM method of Bekker & Davis (PMLR v94, 2018).  Use a small covariate
    set: local relief, slope, a gravity-derived basin-fill proxy, lidar coverage
    and distance to range front.  Train with the propensity-aware empirical risk
    of Bekker, Robberechts & Davis (arXiv:1809.03207), weights clipped at 10,
    against an nnPU baseline on identical folds.

References (public, checked by title/venue; the sandbox cannot reach the
publisher hosts, so the bibliographic strings below are asserted by the brief
and are NOT independently fetched here -- see ``docs/research/limitations.md``):

* Jaskie Bekker, Jesse Davis, "Learning from Positive and Unlabeled Data with a
  Selection Bias", PMLR v94 (ICLR Workshop / AISTATS-era volume), 2018.
* Jaskie Bekker, Pieter Robberechts, Jesse Davis, "Beyond the Selected Completely
  at Random Assumption for Learning from Positive and Unlabeled Data",
  arXiv:1809.03207 (ECML-PKDD 2019).
* Ryuichi Kiryo et al., "Positive-Unlabeled Learning with Non-Negative Risk",
  NeurIPS 2017 (the nnPU baseline).

Shared tooling (``gems57.*``) is copied verbatim from the family template
``buffedlizard55-lab/60GEMSDOE`` commit 6444fa6552335190f0bc89661acf725ed73e7fcb;
see ``src/gems57/PROVENANCE.md``.  Nothing in ``gems57`` is modified here.
"""

__version__ = "1.0.0"

LANE_ID = "GEMSDOE65-SAR-PU"
