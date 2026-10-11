import numpy as np
import pytest
from gems65.common import verify_template
from gems57 import metric, spatial, evaluate_holdout, uniqueness


def test_no_private_template_fork():
    assert verify_template()['files']


def test_exact_metric_matches_bruteforce():
    rng=np.random.default_rng(32)
    p=rng.random((11,12));p[p<.7]=0
    truth=rng.random((11,12))<.1
    a=metric.dti_exact(p,truth)
    b=metric.dti_bruteforce(p,truth)
    assert a['dti']==pytest.approx(b['dti'],abs=1e-9)


def test_visible_faults_are_pixel_exact_not_buffer_masked():
    p=np.zeros((21,21));g=np.zeros_like(p,bool);v=np.zeros_like(g)
    g[11,10]=1;v[10,10]=1;p[10,10]=1;p[11,10]=1
    fold=dict(region=np.ones_like(g),visible=v,truth=g)
    result,terms=evaluate_holdout.evaluate(p,fold,np.ones_like(g),block_side=5)
    assert result['dti']==pytest.approx(1)
    assert terms[:,3].sum()==1
    assert result['n_emitted']==1


def test_whole_component_tail_removed_and_buffered():
    cat=np.zeros((80,80),bool);cat[10,10:15]=1;cat[60,60:66]=1
    cat[35:45,35]=1  # Crosses horizontal quadrant boundary.
    fp=np.ones_like(cat)
    for fold in spatial.folds(cat,fp,buffer_px=3):
        held=fold['held_all'];train=fold['train']
        assert not np.any(held&fold['visible'])
        assert not np.any(train&held)
        assert not np.any(train&fold['region'])
        if fold['truth'][35:45,35].any():assert held[35:45,35].all()


def test_pooled_bootstrap_requires_identical_truth_counts():
    a=np.array([[1,1,1,2],[1,2,1,2]],float);b=a.copy();b[1,3]=3
    with pytest.raises(ValueError):evaluate_holdout.pooled_summary({'sar':a,'nnpu':b},candidate='sar')


def test_pooled_bootstrap_identical_arms_have_zero_difference():
    a=np.array([[1,1,1,2],[1,2,1,2],[0,7,0,0]],float)
    r=evaluate_holdout.pooled_summary({'sar':a,'nnpu':a.copy()},candidate='sar',draws=50)
    assert r['paired_differences']['nnpu']['ci95']==[0,0]
    assert r['bootstrap']['clusters']==3  # Negative-only FP cluster is retained.


def test_literal_overlap_has_no_saturated_prior_exemption():
    mine=np.zeros((15,15));mine[7,7]=1
    assert uniqueness.dot_overlap(mine,np.ones_like(mine))==1
    theirs=np.zeros_like(mine);theirs[7,10]=1
    assert uniqueness.dot_overlap(mine,theirs)==1  # inclusive three-pixel radius
    theirs[:]=0;theirs[7,11]=1
    assert uniqueness.dot_overlap(mine,theirs)==0
