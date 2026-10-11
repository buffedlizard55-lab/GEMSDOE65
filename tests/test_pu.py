import numpy as np
import pytest
from scipy.optimize._numdiff import approx_derivative
from scipy.special import expit
from gems65.pu import (posterior, logistic_objective, propensity_risk, nnpu_risk,
                       Design, weighted_quantile, fit_sar, predict)


def test_posterior_bayes():
    f=np.array([.2,.6,.9]);e=np.array([.1,.5,.8]);s=np.array([1,0,0])
    np.testing.assert_allclose(posterior(f,e,s),[1,.6*.5/(1-.6*.5),.9*.2/(1-.9*.8)])


@pytest.mark.parametrize('bad',[np.nan,-.1,1.1])
def test_bad_posterior(bad):
    with pytest.raises(ValueError):posterior([bad],[.5],[0])


@pytest.mark.parametrize('kind',['logistic','sar','nnpu'])
def test_gradients(kind):
    rng=np.random.default_rng(71)
    x=rng.normal(size=(30,4));t=rng.normal(size=4)/3
    s=np.r_[np.ones(9),np.zeros(21)];w=np.ones(30)/30;e=np.linspace(.1,.9,30)
    if kind=='logistic':fun=lambda b:logistic_objective(b,x,s,w)
    elif kind=='sar':fun=lambda b:propensity_risk(b,x,s,e,w)
    else:fun=lambda b:nnpu_risk(b,x,s,w,.35)
    value,grad=fun(t)
    numeric=approx_derivative(lambda b:np.array([fun(b)[0]]),t).ravel()
    np.testing.assert_allclose(grad,numeric,rtol=1e-5,atol=1e-7)
    assert np.isfinite(value)


def test_known_propensity_risk_expectation_equals_supervised():
    # Analytic expectation over label selection, not a stochastic approximate test.
    x=np.array([[1.,-1],[1,0],[1,2],[1,3.]])
    theta=np.array([-.2,.4]);y=np.array([1,0,1,0]);e=np.array([.2,.4,.8,.7]);w=np.ones(4)/4
    z=x@theta
    averaged=np.logaddexp(0,z) - (y*e)/e*z
    supervised=np.logaddexp(0,z)-y*z
    np.testing.assert_allclose(w@averaged,w@supervised)
    l,_=propensity_risk(theta,x,np.zeros(4),e,w,l2=0)
    np.testing.assert_allclose(l,w@np.logaddexp(0,z))


def test_weight_clipping_changes_risk_as_declared():
    theta=np.array([.5]);x=np.ones((2,1));s=np.array([1.,0]);e=np.array([.01,.5]);w=np.ones(2)/2
    value,_=propensity_risk(theta,x,s,e,w,l2=0)
    assert value==pytest.approx(np.logaddexp(0,.5)-10*.5/2)


def test_nnpu_clamps_negative_component():
    x=np.array([[1.,5],[1,-5.]])
    theta=np.array([0.,2.]);s=np.array([1,0]);w=np.array([.1,.9])
    value,_=nnpu_risk(theta,x,s,w,prior=.8,l2=0)
    assert value>=0
    assert value==pytest.approx(.8*np.logaddexp(0,-10))


def test_weighted_population_not_balanced_sample_scaling():
    x=np.array([[0.,np.nan],[10,10],[20,20]])
    w=np.array([.9,.05,.05]);d=Design.fit(x,w)
    assert d.med[0]==0
    before=d.med.copy();z=d.transform(np.array([[np.nan,1e30]]))
    np.testing.assert_array_equal(before,d.med)
    assert np.isfinite(z).all()
    assert z[0,1]==0


def test_all_missing_training_feature_is_not_invented():
    with pytest.raises(ValueError):Design.fit(np.array([[np.nan],[np.nan]]),np.ones(2))


def test_deterministic_small_sar_and_nnpu():
    rng=np.random.default_rng(15);x=rng.normal(size=(180,12));s=(rng.random(180)<.1).astype(float);w=np.ones(180)/180
    a=fit_sar(x,s,w,max_em=4);b=fit_sar(x,s,w,max_em=4)
    np.testing.assert_array_equal(a['sar_coef'],b['sar_coef'])
    p=predict(a,x)
    assert all(np.isfinite(v).all() and (v>=0).all() and (v<=1).all() for v in p.values())
    assert a['diagnostics']['identifiable'] is False
    assert a['diagnostics']['inverse_weight_cap']==10
