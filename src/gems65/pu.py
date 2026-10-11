"""Auditable CPU SAR-EM, clipped propensity empirical risk, and nnPU.

SAR-EM posterior: Bekker & Davis (PMLR 94, 2018), section 4.1.
Empirical risk: Bekker, Robberechts & Davis, arXiv:1809.03207.
No claim of nonparametric identification: propensity intercept is an assumed
reference-point value, fixed separately in each sensitivity scenario.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit


def weighted_quantile(a, weights, q):
    a, weights = np.asarray(a, float), np.asarray(weights, float)
    if a.shape != weights.shape or a.ndim != 1 or np.any(weights < 0) or not 0 <= q <= 1:
        raise ValueError('Invalid weighted quantile input')
    good = np.isfinite(a) & np.isfinite(weights) & (weights > 0)
    if not good.any():
        raise ValueError('No finite weighted observations')
    a, weights = a[good], weights[good]
    order = np.argsort(a, kind='stable')
    c = np.cumsum(weights[order])
    return float(a[order[min(np.searchsorted(c, q * c[-1]), len(order) - 1)]])


@dataclass
class Design:
    med: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, x, weights):
        x = np.asarray(x, float)
        med = np.array([weighted_quantile(a, weights, .5) for a in x.T])
        lo = np.array([weighted_quantile(a, weights, .25) for a in x.T])
        hi = np.array([weighted_quantile(a, weights, .75) for a in x.T])
        return cls(med, np.where(hi - lo > 1e-6, hi - lo, 1.0))

    def standardize(self, x):
        x = np.asarray(x, float)
        if x.ndim != 2 or x.shape[1] != len(self.med):
            raise ValueError('Feature count mismatch')
        x = np.where(np.isfinite(x), x, self.med)
        return np.clip((x - self.med) / self.scale, -6, 6)

    def transform(self, x):
        z = self.standardize(x)
        return np.column_stack([np.ones(len(z)), z, .25 * z * z])


def posterior(f, e, s):
    f, e, s = map(lambda a: np.asarray(a, float), (f, e, s))
    if f.shape != e.shape or f.shape != s.shape or not np.isfinite([f, e, s]).all():
        raise ValueError('Invalid posterior arrays')
    if np.any((f < 0) | (f > 1) | (e <= 0) | (e >= 1)) or not np.isin(s, [0, 1]).all():
        raise ValueError('Invalid PU probabilities / labels')
    return np.where(s == 1, 1., f * (1 - e) / np.maximum(1 - f * e, 1e-15))


def logistic_objective(theta, x, target, weights, l2=1e-4, offset=0.):
    z = x @ theta + offset
    loss = np.logaddexp(0, z) - target * z
    return (float(weights @ loss + .5 * l2 * (theta @ theta)),
            x.T @ (weights * (expit(z) - target)) + l2 * theta)


def propensity_risk(theta, x, s, e, weights, l2=1e-4, cap=10.):
    if cap <= 0 or np.any(e <= 0) or np.any(e > 1):
        raise ValueError('Invalid propensity or weight cap')
    # ell0 + (s/e)*(ell1-ell0) = softplus(z) - (s/e)*z.
    target = s * np.minimum(1 / e, cap)
    return logistic_objective(theta, x, target, weights, l2)


def nnpu_risk(theta, x, s, weights, prior, l2=1e-4):
    if not 0 < prior < 1 or not np.any(s == 1):
        raise ValueError('nnPU requires positives and a prior in (0,1)')
    z = x @ theta
    p = expit(z)
    wpos = weights * s
    wpos = wpos / wpos.sum()
    positive = prior * (wpos @ np.logaddexp(0, -z))
    negative = weights @ np.logaddexp(0, z) - prior * (wpos @ np.logaddexp(0, z))
    grad = x.T @ (prior * wpos * (p - 1))
    if negative > 0:
        grad += x.T @ ((weights - prior * wpos) * p)
    return (float(positive + max(0., negative) + .5 * l2 * (theta @ theta)), grad + l2 * theta)


def _solve(fun, initial, args):
    result = minimize(fun, initial, args=args, jac=True, method='L-BFGS-B',
                      bounds=[(-20, 20)] * len(initial),
                      options={'maxiter':150, 'ftol':1e-10, 'gtol':1e-6})
    if not np.isfinite(result.x).all() or not np.isfinite(result.fun):
        raise ValueError('Nonfinite optimization result')
    return result.x, dict(success=bool(result.success), iterations=int(result.nit),
                          objective=float(result.fun), message=str(result.message))


def fit_sar(x, s, weights, reference_propensity=.5, l2=1e-4, max_em=25):
    x, s, weights = np.asarray(x, float), np.asarray(s, float), np.asarray(weights, float)
    if x.ndim != 2 or x.shape[1] < 5 or s.shape != weights.shape or len(x) != len(s):
        raise ValueError('Invalid PU training shapes')
    if not np.isin(s, [0, 1]).all() or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('Positive finite sampling weights and binary observed labels required')
    weights = weights / weights.sum()
    mu = float(weights @ s)
    if not 0 < mu < reference_propensity < 1:
        raise ValueError('Reference propensity must exceed observed positive fraction')
    design = Design.fit(x, weights)
    xf = design.transform(x)
    xe = design.standardize(x)[:, :5]
    intercept = float(logit(reference_propensity))
    ftheta = np.zeros(xf.shape[1]); ftheta[0] = logit(mu / reference_propensity)
    etheta = np.zeros(5)
    history, solver_ok, converged = [], True, False
    for iteration in range(max_em):
        f, e = expit(xf @ ftheta), expit(xe @ etheta + intercept)
        e = np.clip(e, 1e-8, 1 - 1e-8)
        q = posterior(f, e, s)
        ftheta, fr = _solve(logistic_objective, ftheta, (xf, q, weights, l2))
        # Conditional likelihood of selection among expected positives only.
        ew = weights * q; ew /= ew.sum()
        etheta, er = _solve(logistic_objective, etheta, (xe, s, ew, l2, intercept))
        e2 = np.clip(expit(xe @ etheta + intercept), 1e-8, 1 - 1e-8)
        delta = float(weights @ np.abs(e2 - e))
        f2 = expit(xf @ ftheta)
        ps = np.clip(f2 * e2, 1e-12, 1 - 1e-12)
        observed_ll = float(weights @ (s * np.log(ps) + (1 - s) * np.log1p(-ps)))
        history.append(dict(iteration=iteration + 1, mean_abs_propensity_change=delta,
                            observed_log_likelihood=observed_ll, outcome_solver=fr, propensity_solver=er))
        solver_ok &= fr['success'] and er['success']
        if iteration >= 4 and delta < 1e-4:
            converged = True
            break
    e = np.clip(expit(xe @ etheta + intercept), 1e-8, 1 - 1e-8)
    iw = np.minimum(1 / e, 10.)
    prior = float(weights @ (s * iw))
    if not 0 < prior < 1:
        raise ValueError('Corrected positive mass is not a valid nnPU prior')
    risk_theta, rr = _solve(propensity_risk, ftheta, (xf, s, e, weights, l2, 10.))
    initial = np.zeros(xf.shape[1]); initial[0] = logit(prior)
    nn_theta, nr = _solve(nnpu_risk, initial, (xf, s, weights, prior, l2))
    diagnostics = dict(reference_propensity=reference_propensity, reference='training weighted median covariates (standardized z=0)',
        identifiable=False, scale_assumption_only=True, observed_label_fraction=mu,
        clipped_positive_mass_prior=prior, inverse_weight_cap=10.,
        positive_weight_clip_fraction=float(np.sum(weights * s * (1 / e > 10)) / mu),
        propensity_training_range=[float(e.min()), float(e.max())], em_iterations=len(history),
        em_converged=converged, all_optimizers_success=bool(solver_ok and rr['success'] and nr['success']),
        risk_solver=rr, nnpu_solver=nr, em_history=history,
        caveat='Fixed propensity intercept is a sensitivity assumption, not identified mapping completeness; finite-iteration estimate.')
    return dict(design=design, propensity_coef=etheta, propensity_intercept=intercept,
                sar_coef=risk_theta, nnpu_coef=nn_theta, diagnostics=diagnostics)


def predict(model, x):
    d = model['design']
    xf = d.transform(x)
    return dict(sar=expit(xf @ model['sar_coef']).astype('float32'),
                nnpu=expit(xf @ model['nnpu_coef']).astype('float32'),
                propensity=expit(d.standardize(x)[:, :5] @ model['propensity_coef'] + model['propensity_intercept']).astype('float32'))
