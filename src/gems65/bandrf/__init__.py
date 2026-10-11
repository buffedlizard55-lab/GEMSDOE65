"""Lane 65 "bandrf" arm: SAR propensity + the declared splay-band emission rule.

This package is the implementation that produced ``evidence/lane65-bandrf/`` and the
candidate in ``docs/downloads/``.  It is deliberately self-contained and imports the shared
template (``gems57``) rather than forking it.  It is a *second* lane: the canonical lane of
this repository lives in ``gems65.{pu,holdout,gate,emission,...}`` and reached a negative
verdict with a different instrument; this one is published alongside it, with its own run
card, because the two instruments disagree (see ``docs/lane65-bandrf/`` and IR-65-025).
"""
