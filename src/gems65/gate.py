"""Only complete evidence can authorize a download; never a weekly slot."""
from __future__ import annotations


def decide(holdout, high_tercile, *, canary_ok, unique, format_ok, incumbent_verified,
           registry_complete, optimization_ok):
    reasons = []
    for name, report, strict in [('overall', holdout, True), ('highest_propensity_tercile', high_tercile, False)]:
        try:
            d = report['paired_differences']['nnpu']
            delta, lower = d['delta'], d['ci95'][0]
            passed = (delta > 0 and lower > 0) if strict else (delta >= 0 and lower >= 0)
        except (KeyError, TypeError, IndexError):
            passed = False
        if not passed:
            reasons.append(f'{name}_improvement_not_established')
    for k, ok in [('leakage_canary', canary_ok), ('registry_uniqueness', unique),
                  ('format', format_ok), ('comparable_incumbent', incumbent_verified),
                  ('complete_registry', registry_complete), ('optimization', optimization_ok)]:
        if ok is not True:
            reasons.append(k + '_not_cleared')
    return dict(verdict='negative' if reasons else 'promote', eligible_for_download=not reasons,
                approved_for_weekly_slot=False, submission_slots_used=0, reasons=reasons)
