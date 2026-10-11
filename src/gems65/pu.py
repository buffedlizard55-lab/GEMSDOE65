"""Propensity-aware empirical risk for PU data, and the nnPU baseline.

Source (consulted 2026-10-11):
    Jessa Bekker, Pieter Robberechts, Jesse Davis.
    "Beyond the Selected Completely At Random Assumption for Learning from
    Positive and Unlabeled Data."  ECMLPKDD 2019, LNCS pp. 71-85.
    arXiv:1809.03207 · https://arxiv.org/abs/1809.03207
    Author copy: https://people.cs.kuleuven.be/~pieter.robberechts/repo/Bekker2019_ECMLPKDD_SARPU.pdf
    DOI: 10.1007/978-3-030-46147-8_5

The estimator, and where each term comes from
---------------------------------------------
The paper's counting insight: "for each labeled example (x_i, s = 1) that has a
propensity score e_i, there are expected to be 1/e_i positive examples, of which
1/e_i - 1 did not get selected to be labeled."  Its bias identity is

    bias( R_hat(yhat | ehat, s) ) = (1/n) * sum_i  y_i (1 - e_i) ( d1(yhat_i) - d0(yhat_i) )

with ``d1``/``d0`` the per-example costs of predicting positive/negative.
Subtracting that identity from the naive weighted risk collapses, for the
logistic loss, to this exact per-row weighting (derivation:

    (1/e)L1 - ((1-e)/e)(L1 - L0)  =  L1 + ((1-e)/e)L0              ):

    R_hat_SAR(g) = (1/n) [ sum_{i: s=1} L(g(x_i), 1)
                         + sum_{i: s=1} ((1-e_i)/e_i) L(g(x_i), 0)
                         + sum_{i: s=0} L(g(x_i), 0) ]  + (1/(2C))||beta||^2

So the SAR risk is ordinary weighted logistic regression on three row groups:
labelled positives (as positives, weight 1), the same labelled positives (as
negatives, weight ``(1-e)/e``), and the unlabelled rows (as negatives, weight 1).
The second row group is precisely the "expected unselected positives" the paper
counts.

**Weights clipped at 10** (the lane paragraph's requirement).
    w_i = (1 - e_i)/e_i is clipped to [0, 10].  Clipping a propensity weight is
    standard practice to control the variance of an inverse-probability
    estimator; the same device appears as "propensity clipping" in Schnabel et
    al. (2016), "Recommendations as Treatments: Debiasing Learning and
    Evaluation", arXiv:1602.05352, sec. 5.1 ("clipping the propensity weights").
    Clipping *biases* the estimator, which is why the full sensitivity curve is
    reported rather than one number.

The nnPU baseline (on identical folds)
--------------------------------------
    Kiryo, Niu, du Plessis, Sugiyama. "Positive-Unlabeled Learning with
    Non-negative Risk Estimator." NeurIPS 2017. arXiv:1703.00593

    R_hat_nnPU(g) = pi * R_hat_P^+(g) + max(0, R_hat_U^-(g) - pi * R_hat_P^-(g))

Both arms use the **same** hypothesis class (L2 logistic regression with the same
``C``), the **same** rows, and the **same** folds.  The only difference is how
the risk is reweighted: a single constant ``pi`` for the baseline, a per-example
function ``e(x)`` for the SAR arm.  That is exactly the contrast the lane
paragraph asks for.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

__all__ = ["W_CLIP", "LogisticModel", "weighted_logistic_fit",
           "propensity_weighted_fit", "nnpu_fit", "scar_fit", "logloss"]

W_CLIP: float = 10.0


def logloss(z: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Binary logistic loss for labels in ``{0, 1}``.

        L(z, 1) = logaddexp(0, -z) = log(1 + exp(-z))
        L(z, 0) = logaddexp(0, +z) = log(1 + exp(+z))

    Both branches are numerically stable softplus forms; the gradient in both
    cases is ``sigmoid(z) - y``.

    .. warning:: an earlier revision used ``logaddexp(0, -(2y-1) z)``, which is
       the correct *{0,1}* loss only when labels are encoded as ``{-1, +1}``.
       With ``y = 0`` that expression is identically ``log 2``, so the objective
       did not grow as ``z -> +inf`` for negatives: L-BFGS-B returned
       ``status 2 (ABNORMAL)`` after 0-2 iterations with ``beta = 0`` and every
       model in both arms predicted a constant 0.5 (AUC 0.5).  Caught by the
       synthetic recovery test in ``tests/test_pu.py``.  The gradient was
       already correct, so the bug was invisible in any gradient-free check.
    """
    z = np.asarray(z, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    return np.where(y > 0.5, np.logaddexp(0.0, -z), np.logaddexp(0.0, z))


def _sigmoid(z):
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


@dataclass
class LogisticModel:
    """L2 logistic regression fitted by L-BFGS on an explicit risk objective.

    Written out here rather than hidden behind a library so that the *risk* the
    model minimises is the object under test.  sklearn's ``sample_weight``
    normalisation makes the two arms' objectives non-comparable; this does not.
    """

    beta: np.ndarray
    n_features: int
    name: str = "logistic"
    objective_value: float = float("nan")
    nit: int = 0
    converged: bool = False

    def decision(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float64)
        return X @ self.beta[: self.n_features] + self.beta[self.n_features]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        p1 = _sigmoid(self.decision(X))
        return np.column_stack([1.0 - p1, p1])

    @property
    def coef_(self) -> np.ndarray:
        return self.beta[: self.n_features][None, :]

    @property
    def intercept_(self) -> np.ndarray:
        return np.array([self.beta[self.n_features]])


def _aug(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=np.float64)
    return np.column_stack([X, np.ones(X.shape[0])])


def weighted_logistic_fit(X: np.ndarray, y: np.ndarray, w: np.ndarray, *,
                          C: float = 1.0, max_iter: int = 200,
                          name: str = "weighted_logistic",
                          ) -> LogisticModel:
    """Plain weighted L2 logistic regression, fitted on its own explicit risk.

    Objective: ``(1/n) sum_i w_i * logloss(z_i, y_i) + (1/(2C)) ||beta||^2``.
    Provided so that every model in this repository is fitted by the same
    auditable optimiser and no library's internal weight normalisation can make
    two arms non-comparable.
    """
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64).reshape(-1)
    w = np.asarray(w, dtype=np.float64).reshape(-1)
    Xa = _aug(X)
    n = y.size
    if y.min() == y.max():
        raise ValueError("weighted_logistic_fit needs both classes present")

    def obj(beta):
        z = Xa @ beta
        L = logloss(z, y)
        risk = float((w * L).sum() / n) + 0.5 * (beta @ beta) / C
        g = Xa.T @ (w * (_sigmoid(z) - y)) / n + beta / C
        return risk, g

    # warm start on the unweighted problem
    def obj0(b0):
        L = logloss(Xa @ b0, y)
        return float(L.mean()) + 0.5 * (b0 @ b0) / C, Xa.T @ (_sigmoid(Xa @ b0) - y) / n + b0 / C

    r0 = minimize(obj0, np.zeros(Xa.shape[1]), jac=True, method="L-BFGS-B",
                  options={"maxiter": 100})
    res = minimize(obj, r0.x, jac=True, method="L-BFGS-B", options={"maxiter": max_iter})
    return LogisticModel(beta=res.x, n_features=X.shape[1], name=name,
                         objective_value=float(res.fun), nit=int(res.nit),
                         converged=bool(res.success or res.nit < max_iter))


def propensity_weighted_fit(X: np.ndarray, s: np.ndarray, e: np.ndarray, *,
                            C: float = 1.0, w_clip: float = W_CLIP,
                            max_iter: int = 250,
                            class_prior: float | None = None,
                            ) -> tuple[LogisticModel, np.ndarray]:
    """Fit the propensity-aware empirical risk of Bekker, Robberechts & Davis.

    Returns ``(model, f_train)`` where ``f_train = Pr(y=1|x)`` on the training
    rows.  ``e`` is the per-row propensity (from :mod:`gems65.propensity`).
    """
    X = np.asarray(X, dtype=np.float64)
    s = np.asarray(s).astype(np.int8).reshape(-1)
    e = np.clip(np.asarray(e, dtype=np.float64).reshape(-1), 1e-6, 1.0)
    lab = s == 1
    unl = ~lab
    n = s.size
    if lab.sum() == 0 or unl.sum() == 0:
        raise ValueError("need both labelled and unlabelled rows")

    Xa = _aug(X)
    d = Xa.shape[1]
    w_pos_zero = np.clip((1.0 - e) / e, 0.0, w_clip)  # the clipped 1/e - 1 count

    Xp, Xz, Xu = Xa[lab], Xa[lab], Xa[unl]
    w_z = w_pos_zero[lab]

    def obj(beta):
        zp = Xp @ beta
        zz = Xz @ beta
        zu = Xu @ beta
        Lp = logloss(zp, np.ones(zp.size))
        Lz = logloss(zz, np.zeros(zz.size))
        Lu = logloss(zu, np.zeros(zu.size))
        risk = (Lp.sum() + (w_z * Lz).sum() + Lu.sum()) / n
        pen = 0.5 * (beta @ beta) / C
        # gradient
        sp = _sigmoid(zp) - 1.0
        sz = _sigmoid(zz) - 0.0
        su = _sigmoid(zu) - 0.0
        g = (Xp.T @ sp + Xz.T @ (w_z * sz) + Xu.T @ su) / n + beta / C
        return risk + pen, g

    beta0 = np.zeros(d)
    # warm start: unweighted logistic on labelled-vs-unlabelled
    y0 = lab.astype(np.float64)
    Xa0 = Xa

    def obj0(b0):
        z = Xa0 @ b0
        L = logloss(z, y0)
        sp = _sigmoid(z) - y0
        return L.mean() + 0.5 * (b0 @ b0) / C, Xa0.T @ sp / Xa0.shape[0] + b0 / C

    r0 = minimize(obj0, beta0, jac=True, method="L-BFGS-B",
                  options={"maxiter": 100})
    res = minimize(obj, r0.x, jac=True, method="L-BFGS-B",
                   options={"maxiter": max_iter})
    m = LogisticModel(beta=res.x, n_features=X.shape[1], name="propensity_weighted",
                      objective_value=float(res.fun), nit=int(res.nit),
                      converged=bool(res.success or res.nit < max_iter))
    return m, m.predict_proba(X)[:, 1]


def nnpu_fit(X: np.ndarray, s: np.ndarray, *, pi: float, C: float = 1.0,
             max_iter: int = 250) -> tuple[LogisticModel, np.ndarray, dict]:
    """Non-negative PU risk estimator (Kiryo et al. 2017), same class and folds."""
    X = np.asarray(X, dtype=np.float64)
    s = np.asarray(s).astype(np.int8).reshape(-1)
    lab = s == 1
    unl = ~lab
    np_lab = int(lab.sum())
    np_unl = int(unl.sum())
    if np_lab == 0 or np_unl == 0:
        raise ValueError("need both labelled and unlabelled rows")
    Xa = _aug(X)
    Xp, Xu = Xa[lab], Xa[unl]
    d = Xa.shape[1]
    trace: dict = {"clamped_steps": 0, "negative_risk_final": None}

    def obj(beta):
        zp, zu = Xp @ beta, Xu @ beta
        Lp_pos = logloss(zp, np.ones(np_lab))
        Lp_neg = logloss(zp, np.zeros(np_lab))
        Lu_neg = logloss(zu, np.zeros(np_unl))
        r_p_pos = Lp_pos.mean()
        r_p_neg = Lp_neg.mean()
        r_u_neg = Lu_neg.mean()
        inner = r_u_neg - pi * r_p_neg
        risk = pi * r_p_pos + max(0.0, inner)
        pen = 0.5 * (beta @ beta) / C
        sp = _sigmoid(zp) - 1.0
        spn = _sigmoid(zp) - 0.0
        sun = _sigmoid(zu) - 0.0
        g = pi * (Xp.T @ sp) / np_lab + beta / C
        if inner > 0.0:
            g = g + (Xu.T @ sun) / np_unl - pi * (Xp.T @ spn) / np_lab
            trace["last_clamped"] = False
        else:
            trace["last_clamped"] = True
        return risk + pen, g

    def obj0(b0):
        z = Xa @ b0
        y0 = lab.astype(np.float64)
        L = logloss(z, y0)
        return L.mean() + 0.5 * (b0 @ b0) / C, Xa.T @ (_sigmoid(z) - y0) / Xa.shape[0] + b0 / C

    r0 = minimize(obj0, np.zeros(d), jac=True, method="L-BFGS-B", options={"maxiter": 100})
    res = minimize(obj, r0.x, jac=True, method="L-BFGS-B", options={"maxiter": max_iter})
    beta = res.x
    zp, zu = Xp @ beta, Xu @ beta
    r_p_pos = float(logloss(zp, np.ones(np_lab)).mean())
    r_p_neg = float(logloss(zp, np.zeros(np_lab)).mean())
    r_u_neg = float(logloss(zu, np.zeros(np_unl)).mean())
    trace["negative_risk_final"] = r_u_neg - pi * r_p_neg
    trace["r_p_pos"] = r_p_pos
    trace["r_p_neg"] = r_p_neg
    trace["r_u_neg"] = r_u_neg
    m = LogisticModel(beta=beta, n_features=X.shape[1], name="nnpu",
                      objective_value=float(res.fun), nit=int(res.nit),
                      converged=bool(res.success or res.nit < max_iter))
    return m, m.predict_proba(X)[:, 1], trace


def scar_fit(X: np.ndarray, s: np.ndarray, *, c: float,
             C: float = 1.0, w_clip: float = W_CLIP,
             max_iter: int = 250) -> tuple[LogisticModel, np.ndarray]:
    """SCAR special case: the same SAR risk with ``e(x)`` replaced by a constant.

    This is the honest "SCAR arm" for the ablation -- identical code path, one
    number instead of a function.  It is the estimator the literature means when
    it says a PU learner "assumes the labelled positives are a random subsample".
    """
    e = np.full(np.asarray(s).shape, float(c))
    return propensity_weighted_fit(X, s, e, C=C, w_clip=w_clip, max_iter=max_iter)
