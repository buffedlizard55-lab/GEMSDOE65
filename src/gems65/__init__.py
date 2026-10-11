"""Selection-bias-aware fault detection; no competition upload API.

Lane 65 (session 2026-10-11) adds the SAR propensity/EM stack used by ``scripts/02_run_holdout.py``,
``scripts/03_build_submission.py`` and ``scripts/07_adjudicate.py``, alongside the canonical modules
(``common``, ``gate``, ``canary``, ``pu``).  Everything lives in this one package: no private forks.

See ``README.md`` for the standing brief, ``docs/index.html`` for the canonical site and
``docs/lane65/index.html`` for the lane-65 result pages, ``evidence/run_card.json`` for the canonical
run card and ``RUN_CARD.json`` for the lane-65 run card, and ``registry/irregularities.json`` for
every irregularity raised with its evidence and disposition.
"""

__version__ = "1.0.0"
