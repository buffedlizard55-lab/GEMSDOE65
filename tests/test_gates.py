import copy
import pytest
from gems65.gate import decide


def report(delta=.01,lo=.001):
    return {'paired_differences':{'nnpu':{'delta':delta,'ci95':[lo,.03]}}}


def good():
    return dict(holdout=report(),high_tercile=report(),canary_ok=True,unique=True,
                format_ok=True,incumbent_verified=True,registry_complete=True,optimization_ok=True)


def test_pass_is_only_selector_eligible_not_slot_approved():
    r=decide(**good());assert r['verdict']=='promote'
    assert r['eligible_for_download'] and not r['approved_for_weekly_slot']
    assert r['submission_slots_used']==0


@pytest.mark.parametrize('key',['canary_ok','unique','format_ok','incumbent_verified','registry_complete','optimization_ok'])
@pytest.mark.parametrize('bad',[False,None,'true'])
def test_missing_or_false_gate_always_blocks(key,bad):
    kw=good();kw[key]=bad
    assert not decide(**kw)['eligible_for_download']


def test_stratum_loss_blocks_overall_win():
    kw=good();kw['high_tercile']=report(-.01,-.02)
    assert decide(**kw)['verdict']=='negative'


def test_point_estimate_win_with_ci_crossing_zero_blocks():
    kw=good();kw['holdout']=report(.01,-.01)
    assert decide(**kw)['verdict']=='negative'


def test_unknown_results_are_not_zero_scores():
    kw=good();kw['holdout']=None
    assert decide(**kw)['verdict']=='negative'
