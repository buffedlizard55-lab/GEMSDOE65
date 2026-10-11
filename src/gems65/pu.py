"""Selection-bias-aware (SAR) PU learning: EM propensity estimation + propensity-weighted ERM.

Every formula below is transcribed from the primary source and nothing else.

SOURCE A -- Bekker & Davis (2018), "Learning from Positive and Unlabeled Data under the
Selected At Random Assumption", Proceedings of the Second International Workshop on Learning
with Imbalanced Domains: Theory and Applications, PMLR 94:8-22.
    https://proceedings.mlr.press/v94/bekker18a.html      [verified 2026-10-11]

SOURCE B -- Bekker, Robberechts & Davis, "Beyond the Selected Completely At Random Assumption
for Learning from Positive and Unlabeled Data", arXiv:1809.03207 (ECML-PKDD 2019).
    https://arxiv.org/abs/1809.03207                      [verified 2026-10-11]
    PDF used for the transcriptions: https://jessa.github.io/assets/pdf/bekker2019ecml.pdf

Transcriptions (quotation-level fidelity, section by section):

* Definition 1 (SOURCE B, sec. 4):  e(x) = Pr(s = 1 | y = 1, x).

* Definition 2, Propensity-Weighted Estimator (SOURCE B, sec. 4.1), verbatim:

      R_hat(y_hat | e, s) = (1/n) sum_i  s_i [ (1/e_i) d1(y_hat_i) + (1 - 1/e_i) d0(y_hat_i) ]
                                     + (1 - s_i) d0(y_hat_i)

  proved unbiased there (E[R_hat] = R(y_hat|y)), with log loss
  d1(y_hat) = -ln y_hat, d0(y_hat) = -ln(1 - y_hat).  No class prior appears in this estimator:
  the propensity carries the missing-mass correction.  The brief's "weights clipped at 10" is
  applied to c_i = 1/e_i, which is exactly the variance knob Proposition 3 bounds.

* EM for propensity estimation (SOURCE B, sec. 5.2), verbatim:

      E-step:   y_hat_i = s_i + (1 - s_i) * f_hat(x_i) (1 - e_hat(x_i)) / (1 - f_hat(x_i) e_hat(x_i))
      M-step f: argmax_f sum_i [ y_hat_i ln f(x_i) + (1 - y_hat_i) ln(1 - f(x_i)) ]
      M-step e: argmax_e sum_i y_hat_i [ s_i ln e(x_i) + (1 - s_i) ln(1 - e(x_i)) ]

  i.e. f is a weighted logistic regression with soft targets y_hat_i on the classifier
  attributes x, and e is a weighted logistic regression with target s_i and weight y_hat_i on
  the PROPENSITY attributes x_e only (sec. 5.1: "the propensity function only depends on a
  subset of the attributes x_e").  Initialisation, verbatim: "The classification model is
  initialized by fitting a balanced model which considers the unlabeled examples as negative.
  The propensity score model is initialized by using the classification model to estimate the
  probabilities of each unlabeled example being positive."  Convergence, verbatim: both the log
  likelihood and the propensity model must converge, the latter measured by "the average slope
  of the minimum square error line through the propensity score prediction of the last n
  iterations".  This module implements exactly that stopping rule.

* SOURCE B sec. 5.2 closing advice, implemented as ``fit_propensity_aware_erm``: "In that case,
  it is advisable to retrain the classifier with the obtained propensity score, using the
  propensity-weighted risk estimation method."

BASELINE -- nnPU (Kiryo et al. 2017, arXiv:1603.07419), the SCAR non-negative PU risk:

      R_PU  = pi * E_P[d1] + E_U[d0] - pi * E_P[d0]
      R_nn  = R_PU                     if R_PU >= -gamma
            = -gamma - 4 * R_PU        otherwise   (gradient ascent on the negative risk)

BASE LEARNER.  Both arms use the SAME hypothesis class: a logistic model on random-Fourier
features of the robustly standardised inputs, i.e. f(x) = sigmoid(w . z(x) + b) with
z(x) = [cos/sin(omega . phi(x))].  This keeps both risks linear in the per-example losses, so
Definition 2 and nnPU are applied EXACTLY (no sample-weight approximations), while still being
a nonlinear function of the raw attributes.  Analytic gradients are used with L-BFGS-B.

IDENTIFIABILITY.  Propensity is not identified from PU data alone (SOURCE B sec. 2 and 5.1;
also stated in the brief).  ``anchor_propensity`` therefore re-scales the fitted propensity by
an intercept shift so that the mean propensity over labelled positives equals a target value
a_bar, and the pipeline reports results over a grid of a_bar as a sensitivity analysis rather
than claiming a point identification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

E_MIN = 1e-3
E_MAX = 1.0 - 1e-6
W_CLIP = 10.0        # brief: "weights clipped at 10" -> c = min(1/e, 10)
GAMMA_NNPU = 1.0     # Kiryo et al. default


# -------------------------------------------------------------------------------------------- utils
def sigmoid(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.tanh(0.5 * np.clip(z, -60.0, 60.0)))


def _logloss_parts(p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """d1 = -ln p and d0 = -ln(1-p), clipped for numerical safety (0 < p < 1 assumed)."""
    pc = np.clip(p, 1e-12, 1.0 - 1e-12)
    return -np.log(pc), -np.log1p(-pc)


@dataclass
class RFF:
    """Random-Fourier-feature map: robust standardise -> clip -> cos/sin basis."""
    med: np.ndarray
    iqr: np.ndarray
    omega: np.ndarray
    bias: np.ndarray
    clip: float = 5.0

    @staticmethod
    def fit(X: np.ndarray, n_features: int = 96, gamma: float | None = None, seed: int = 0) -> "RFF":
        med = np.median(X, axis=0)
        q1, q3 = np.percentile(X, [25, 75], axis=0)
        iqr = np.maximum(q3 - q1, 1e-6)
        Z = np.clip((X - med) / iqr, -5.0, 5.0)
        if gamma is None:
            # median heuristic on a subsample
            sub = Z[np.random.default_rng(seed).choice(len(Z), size=min(3000, len(Z)), replace=False)]
            d2 = ((sub[:, None, :] - sub[None, :, :]) ** 2).sum(-1)
            gamma = 1.0 / float(np.median(d2[d2 > 0]))
        rng = np.random.default_rng(seed + 1)
        omega = rng.normal(0.0, np.sqrt(2.0 * gamma), size=(Z.shape[1], n_features))
        bias = rng.uniform(0.0, 2.0 * np.pi, size=n_features)
        return RFF(med.astype(np.float64), iqr.astype(np.float64), omega, bias)

    def transform(self, X: np.ndarray) -> np.ndarray:
        Z = np.clip((np.asarray(X, dtype=np.float64) - self.med) / self.iqr, -self.clip, self.clip)
        return np.sqrt(2.0 / self.omega.shape[1]) * np.cos(Z @ self.omega + self.bias)

    def design(self, X: np.ndarray) -> np.ndarray:
        Z = self.transform(X)
        return np.column_stack([np.ones(len(Z)), Z])


@dataclass
class LogisticModel:
    rff: RFF
    theta: np.ndarray = field(default_factory=lambda: np.zeros(1))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return sigmoid(self.rff.design(X) @ self.theta)

    def predict_from_design(self, D: np.ndarray) -> np.ndarray:
        return sigmoid(D @ self.theta)


# ------------------------------------------------------------------------------------- risks (exact)
def propensity_weighted_risk(p: np.ndarray, s: np.ndarray, c: np.ndarray, w: np.ndarray) -> tuple[float, np.ndarray]:
    """Definition 2 with log loss, population weights ``w``, and c = min(1/e, W_CLIP).

    R = sum_i w_i [ s_i ( c_i d1_i + (1 - c_i) d0_i ) + (1 - s_i) d0_i ] / sum_i w_i
    dR/dp_i = w_i [ -s_i c_i / p_i + (s_i (1 - c_i) + (1 - s_i)) / (1 - p_i) ] / sum_i w_i
    """
    d1, d0 = _logloss_parts(p)
    A = s * c
    B = s * (1.0 - c) + (1.0 - s)
    W = float(w.sum())
    R = float(np.sum(w * (A * d1 + B * d0)) / W)
    pc = np.clip(p, 1e-12, 1.0 - 1e-12)
    g = w * (-A / pc + B / (1.0 - pc)) / W
    return R, g


def nnpu_risk(p: np.ndarray, s: np.ndarray, pi: float, w: np.ndarray, gamma: float = GAMMA_NNPU):
    """Non-negative PU risk (Kiryo et al. 2017) with population weights and prior pi."""
    d1, d0 = _logloss_parts(p)
    pos = s > 0.5
    neg = ~pos
    wp = float(w[pos].sum())
    wn = float(w[neg].sum())
    if wp <= 0 or wn <= 0:
        return 0.0, np.zeros_like(p)
    ep_d1 = float(np.sum(w[pos] * d1[pos]) / wp)
    ep_d0 = float(np.sum(w[pos] * d0[pos]) / wp)
    eu_d0 = float(np.sum(w[neg] * d0[neg]) / wn)
    R = pi * ep_d1 + eu_d0 - pi * ep_d0
    pc = np.clip(p, 1e-12, 1.0 - 1e-12)
    gd1 = -1.0 / pc
    gd0 = 1.0 / (1.0 - pc)
    g = np.zeros_like(p)
    g[pos] = w[pos] * pi * (gd1[pos] - gd0[pos]) / wp
    g[neg] = w[neg] * gd0[neg] / wn
    if R < -gamma:                      # non-negative correction: ascend the negative risk
        R = -gamma - 4.0 * R
        g = -4.0 * g
    return float(R), g


def _chain(g_p: np.ndarray, p: np.ndarray, D: np.ndarray) -> np.ndarray:
    """dp/dtheta for logistic: p(1-p) * D^T g_p."""
    return D.T @ (g_p * p * (1.0 - p))


def fit_risk(D: np.ndarray, p0: np.ndarray, s: np.ndarray, w: np.ndarray, risk_fn, l2: float = 1e-3,
             max_iter: int = 200) -> np.ndarray:
    """L-BFGS-B on a risk given as risk_fn(p, s, w) -> (R, dR/dp).  Design D includes intercept."""
    n, d = D.shape
    scale = float(w.sum())

    def fg(theta):
        p = sigmoid(D @ theta)
        R, gp = risk_fn(p, s, w)
        g = _chain(gp, p, D) + l2 * theta * (n / scale)
        g[0] -= l2 * theta[0] * (n / scale)          # do not penalise the intercept
        return R, g

    theta0 = np.zeros(d)
    theta0[0] = float(np.log(max(p0, 1e-6) / max(1.0 - p0, 1e-6)))
    res = minimize(fg, theta0, jac=True, method="L-BFGS-B",
                   options=dict(maxiter=max_iter, ftol=1e-10, gtol=1e-8))
    return res.x


def fit_soft_target_logistic(D: np.ndarray, y: np.ndarray, w: np.ndarray, l2: float = 1e-3,
                             max_iter: int = 200) -> np.ndarray:
    """Weighted logistic regression with soft targets y in [0,1] (the EM M-step for f)."""
    n, d = D.shape
    scale = float(w.sum())

    def fg(theta):
        p = sigmoid(D @ theta)
        pc = np.clip(p, 1e-12, 1 - 1e-12)
        R = -float(np.sum(w * (y * np.log(pc) + (1 - y) * np.log1p(-pc))) / scale)
        g = D.T @ (w * (p - y)) / scale + l2 * theta * (n / scale)
        g[0] -= l2 * theta[0] * (n / scale)
        return R, g

    theta0 = np.zeros(d)
    ybar = float(np.clip(np.sum(w * y) / scale, 1e-6, 1 - 1e-6))
    theta0[0] = np.log(ybar / (1 - ybar))
    res = minimize(fg, theta0, jac=True, method="L-BFGS-B",
                   options=dict(maxiter=max_iter, ftol=1e-11, gtol=1e-9))
    return res.x


# ---------------------------------------------------------------------------------------- EM (SAR)
def em_posterior(f: np.ndarray, e: np.ndarray, s: np.ndarray) -> np.ndarray:
    """E-step of SOURCE B sec. 5.2: y_hat = s + (1-s) f(1-e)/(1 - f e)."""
    f = np.clip(f, 1e-9, 1 - 1e-9)
    e = np.clip(e, E_MIN, E_MAX)
    return s + (1.0 - s) * (f * (1.0 - e)) / (1.0 - f * e)


def _slope_last(values: np.ndarray) -> float:
    """Average slope of the least-squares line through the last n iterations (SOURCE B sec. 5.2)."""
    v = np.asarray(values, dtype=float)
    if v.size < 2:
        return float("inf")
    x = np.arange(v.size, dtype=float)
    return float(np.polyfit(x, v, 1)[0])


@dataclass
class EMResult:
    theta_f: np.ndarray
    theta_e: np.ndarray
    rff_f: RFF
    rff_e: RFF
    e_raw: np.ndarray
    y_hat: np.ndarray
    history: list
    converged: bool
    n_iter: int


def fit_sar_em(Df: np.ndarray, De: np.ndarray, s: np.ndarray, w: np.ndarray,
               pi_init: float | None = None, max_iter: int = 12, tol_ll: float = 1e-5,
               tol_e_slope: float = 1e-4, slope_window: int = 4, l2: float = 1e-3,
               seed: int = 0, verbose: bool = False) -> EMResult:
    """EM for the classifier f and the propensity e (SOURCE A / SOURCE B sec. 5.2).

    ``Df`` = design matrix on classifier attributes; ``De`` = design on propensity attributes.
    Initialisation follows the paper: f starts as a balanced model treating unlabeled as
    negative; e starts from f's estimate of P(y=1) for the unlabeled examples.
    """
    n = len(s)
    pos = s > 0.5
    # --- init f: "fitting a balanced model which considers the unlabeled examples as negative"
    # (SOURCE B sec. 5.2, verbatim).  Balanced == equal total weight on the two classes, so the
    # intercept starts near 0 and the fit is discriminative rather than prevalence-matched.
    # BUG FIXED 2026-10-11 (IR-65-004): this used to minimise an nnPU risk with pi = 0.5, which is
    # NOT a balanced PN logistic; the EM then fell into the degenerate fixed point f == 0.5
    # everywhere (mean y_hat | s=0 measured 0.4946, log-likelihood monotonically WORSE each
    # iteration: -0.483 -> -0.612 over 8 iterations).
    w_bal = w.copy()
    w_bal[pos] *= float(w[~pos].sum() / max(float(w[pos].sum()), 1e-9))
    theta_f = fit_soft_target_logistic(Df, s, w_bal, l2=l2)
    f = sigmoid(Df @ theta_f)
    # --- init e from f on the unlabeled part
    e_init = np.clip(np.concatenate([np.full(int(pos.sum()), 0.5), f[~pos]]), E_MIN, E_MAX)
    e_full = np.zeros(n)
    e_full[pos] = 0.5
    e_full[~pos] = f[~pos]
    # fit the propensity model to reproduce that initialisation (weighted logistic on x_e)
    y_e = em_posterior(f, np.clip(e_full, 0.05, 0.95), s)
    theta_e = fit_soft_target_logistic(De, s, w * np.clip(y_e, 1e-3, 1.0), l2=l2)
    e = np.clip(sigmoid(De @ theta_e), E_MIN, E_MAX)

    hist = []
    prev_ll = -np.inf
    e_means: list[float] = []
    converged = False
    y_hat = em_posterior(f, e, s)
    for it in range(max_iter):
        # ---- E-step
        y_hat = em_posterior(f, e, s)
        fc = np.clip(f, 1e-12, 1.0 - 1e-12)   # both ends clipped: log1p(-1) = -inf otherwise
        ec = np.clip(e, 1e-12, 1.0 - 1e-12)
        # DIAGNOSTIC FIX 2026-10-11 (IR-65-008): the quantity formerly logged as "ll" is only the
        # f-part of the expected complete-data log-likelihood.  Monotonicity of the f-part alone is
        # NOT guaranteed by EM, so a decreasing trace does not by itself prove non-convergence.
        # The SAR observed-data log-likelihood  sum_i w_i [ s_i log(f_i e_i) + (1-s_i) log(1-f_i e_i) ]
        # is the objective EM must not decrease; both are recorded from here on.
        fe = np.clip(fc * ec, 1e-12, 1.0 - 1e-12)
        ll_f_surrogate = float(np.sum(w * (y_hat * np.log(fc) + (1.0 - y_hat) * np.log1p(-fc))) / float(w.sum()))
        ll = float(np.sum(w * (s * np.log(fe) + (1.0 - s) * np.log1p(-fe))) / float(w.sum()))
        # ---- M-step f : weighted logistic with soft targets y_hat
        theta_f = fit_soft_target_logistic(Df, y_hat, w, l2=l2)
        f = sigmoid(Df @ theta_f)
        # ---- M-step e : weighted logistic on x_e, target s, weight y_hat
        theta_e = fit_soft_target_logistic(De, s, w * np.clip(y_hat, 1e-3, 1.0), l2=l2)
        e = np.clip(sigmoid(De @ theta_e), E_MIN, E_MAX)
        e_means.append(float(np.mean(e[pos])))
        hist.append({"iter": it, "ll_observed": ll, "ll_f_surrogate": ll_f_surrogate, "ll": ll,
                     "mean_e_labelled": e_means[-1],
                     "mean_yhat_unlabelled": float(np.mean(y_hat[~pos]))})
        if verbose:
            print(f"  EM it {it:2d}  ll_obs={ll:+.6f}  ll_f={ll_f_surrogate:+.6f}  mean_e|s=1={e_means[-1]:.4f}  "
                  f"mean_yhat|s=0={hist[-1]['mean_yhat_unlabelled']:.5f}")
        dll = abs(ll - prev_ll)
        slope = abs(_slope_last(e_means[-slope_window:]))
        if it > 0 and dll < tol_ll and (len(e_means) >= slope_window and slope < tol_e_slope):
            converged = True
            break
        prev_ll = ll
    y_hat = em_posterior(f, e, s)
    return EMResult(theta_f, theta_e, None, None, e, y_hat, hist, converged, len(hist))


def anchor_shift(e_raw: np.ndarray, s: np.ndarray, a_bar: float) -> float:
    """Logit intercept shift b with mean(sigmoid(logit(e)+b) | s=1) == a_bar (bisection)."""
    pos = s > 0.5
    ec = np.clip(e_raw[pos], E_MIN, E_MAX)
    lg = np.log(ec / (1.0 - ec))
    lo, hi = -25.0, 25.0
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if float(np.mean(sigmoid(lg + mid))) < a_bar:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def apply_shift(e_raw: np.ndarray, b: float) -> np.ndarray:
    ec = np.clip(np.asarray(e_raw, dtype=np.float64), E_MIN, E_MAX)
    lg = np.log(ec / (1.0 - ec))
    return np.clip(sigmoid(lg + b), E_MIN, E_MAX)


def anchor_propensity(e_raw: np.ndarray, s: np.ndarray, a_bar: float) -> np.ndarray:
    """Intercept-shift e so that mean(e | s = 1) == a_bar.  Scale is not identified from PU data
    alone (SOURCE B sec. 2/5.1), so the pipeline sweeps a_bar and reports a sensitivity, never a
    point estimate.  Returns the re-anchored propensity, clipped to [E_MIN, E_MAX]."""
    pos = s > 0.5
    lg = np.log(np.clip(e_raw[pos], E_MIN, E_MAX) / (1.0 - np.clip(e_raw[pos], E_MIN, E_MAX)))
    lo, hi = -20.0, 20.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if float(np.mean(sigmoid(lg + mid))) < a_bar:
            lo = mid
        else:
            hi = mid
    b = 0.5 * (lo + hi)
    lg_all = np.log(np.clip(e_raw, E_MIN, E_MAX) / (1.0 - np.clip(e_raw, E_MIN, E_MAX)))
    return np.clip(sigmoid(lg_all + b), E_MIN, E_MAX)


def horvitz_thompson_prior(e: np.ndarray, s: np.ndarray, w: np.ndarray) -> float:
    """Population prevalence implied by the propensity: pi = sum_i w_i / e_i over labelled, / N_pop.

    This is the count form of SOURCE B sec. 4 ("for each labeled example with propensity e_i
    there are expected to be 1/e_i positive examples"), used only to set the nnPU baseline's
    prior so that the two arms share a single, documented prevalence.
    """
    pos = s > 0.5
    n_pop = float(w.sum())
    n_pos = float(np.sum(w[pos] / np.clip(e[pos], E_MIN, 1.0)))
    return float(np.clip(n_pos / n_pop, 1e-4, 0.5))


def posterior_from_models(f: np.ndarray, e: np.ndarray) -> np.ndarray:
    """P(y=1 | x, s=0) for an UNLABELLED pixel: f(1-e)/(1 - f e)  (SOURCE B sec. 5.2 E-step)."""
    f = np.clip(f, 1e-12, 1 - 1e-12)
    e = np.clip(e, E_MIN, E_MAX)
    return (f * (1.0 - e)) / (1.0 - f * e)
