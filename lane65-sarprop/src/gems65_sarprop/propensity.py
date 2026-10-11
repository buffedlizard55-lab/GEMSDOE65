"""SAR-EM: estimating the labeling propensity e(x) for selection-biased PU data.

Source (consulted 2026-10-11, verbatim abstract + Algorithm 1 box):
    Jessa Bekker, Jesse Davis.
    "Learning from Positive and Unlabeled Data under the Selected At Random
    Assumption." PMLR 94:8-22, 2018 (LIDTA 2018).
    https://proceedings.mlr.press/v94/bekker18a.html
    PDF: https://proceedings.mlr.press/v94/bekker18a/bekker18a.pdf
    arXiv:1808.08755

What the assumption says (paper, section 3.1)
---------------------------------------------
    e(x) = Pr(s = 1 | y = 1, x)

i.e. the probability that a *genuinely positive* example is selected to be
labelled.  Negative examples are never selected in the PU setting.  SAR is
strictly weaker than SCAR (e(x) == c constant) and strictly stronger than SNAR.

Why this matters here, in one sentence: in the GeoDAWN region a fault is far
more likely to appear in the USGS/INGENIOUS catalogue if someone flew lidar over
it, mapped the quadrangle at 1:24,000, or could actually see the scarp in steep
relief -- so the catalogue's *absences* are informative about mapping effort, not
only about geology.

What is specified vs. what is operationalised
---------------------------------------------
The paper specifies, and this module implements exactly:

* the propensity score definition ``e(x) = Pr(s=1 | y=1, x)``;
* the **propensity-attributes restriction** -- ``e`` depends on a known subset
  ``x_e`` of the attributes ("The first assumption is that the propensity
  function only re[lies on a subset]").  This is the identifiability device: if
  ``e`` could depend on everything, "did not get labelled" and "is not positive"
  would be indistinguishable, which the paper states plainly: "It is an
  ill-defined problem because any unlabeled example can be explained by both a
  low positive class probability and a low labeling probability."
* the **initialisation** described in the companion survey section 5.1: "The
  classification model is initialized by fitting a balanced model which
  considers the unlabeled examples as negative.  The propensity score model is
  initialized by using the classification model to estimate the probabilities of
  each unlabeled example being positive."
* the **convergence criterion**: "Classic EM converges when the log likelihood
  stops improving.  However, the likelihood could stop improving before the
  propensity score model has converged.  Convergence is therefore formulated as
  convergence of both the log likelihood and the propensity model."
* the **counting insight** that drives the M-step (ECMLPKDD companion paper,
  arXiv:1809.03207, which the PMLR paper also uses): "for each labeled example
  (x_i, s = 1) that has a propensity score e_i, there are expected to be 1/e_i
  positive examples, of which 1/e_i - 1 did not get selected to be labeled."
* the **local-certainty parameter d** that appears in Algorithm 1's signature
  (``local certainty parameter d``).

The PMLR paper's Algorithm 1 is printed as a schematic box (``initialize
models``, then alternate ``expectation`` / ``maximization``).  The precise
closed-form M-step updates are not printed in that box, so the two updates used
here are *operationalizations* of the stated design and are labelled as such:

E-step   posterior probability that an unlabeled example is positive, under the
         current (f, e):
             P(y=1 | s=0, x) = f(x)(1 - e(x)) / ( 1 - f(x) e(x) )
         (from P(s=1|x) = e(x) f(x) and Bayes).  Labeled examples are positive
         with probability 1.
M-step 1 the classifier is refitted by *propensity-weighted ERM* (see
         :mod:`gems65_sarprop.pu`) on the same rows, which is the paper's own remedy for
         SAR data.
M-step 2 the propensity model is refitted as a logistic regression of the
         selection indicator ``s`` on ``x_e`` over the pooled *implied positive*
         set: labeled examples enter with s=1 and weight 1; unlabeled examples
         enter with s=0 and weight equal to their E-step posterior.  This is the
         discrete reading of "there are expected to be 1/e_i positives, of which
         1/e_i - 1 did not get selected".

Non-identifiability, handled explicitly
--------------------------------------
Even with the attribute restriction, ``e`` is identified only up to the scale
that the data can see; the paper says so and the schema in this repository
reports the scale as a **sensitivity analysis** rather than asserting a value.
Concretely, ``kappa`` multiplies the fitted propensity and the whole gate is
re-run at kappa in {0.5, 1, 2}.  This is also what the lane paragraph requires
when no exhaustively-mapped public index is reachable: the official GEMS rules
document (docs.nlr.gov/docs/fy26osti/96647.pdf) and the GDR/GBG hosts that would
carry a quadrangle index are unreachable from this sandbox (verified: curl
returns 000), so no anchor is claimed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .pu import weighted_logistic_fit

__all__ = ["SarEmResult", "sar_em", "elkan_noto_label_frequency", "sigmoid"]

E_MIN: float = 1e-3          # floor to keep 1/e finite
W_CLIP: float = 10.0         # the lane's mandated weight clip (see pu.py)


def sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=np.float64)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def _fit_logreg(X: np.ndarray, y: np.ndarray, w: np.ndarray | None = None,
                C: float = 1.0, max_iter: int = 400):
    """Same optimiser as every other model here (gems65_sarprop.pu.weighted_logistic_fit)."""
    n = np.asarray(y).size
    if w is None:
        w = np.ones(n)
    return weighted_logistic_fit(X, y, w, C=C, max_iter=max_iter,
                                 name="em_mstep")


def elkan_noto_label_frequency(f_x: np.ndarray, s: np.ndarray,
                               clip: tuple[float, float] = (1e-3, 1.0)) -> float:
    """Elkan & Noto (2008) estimator of the SCAR label frequency c.

    ``c = mean over labeled positives of f(x)`` when ``f`` predicts
    ``Pr(s=1|x)`` from a model trained with unlabeled examples as negatives.
    Used only to parameterise the SCAR/nnPU *baseline*; the SAR arm estimates a
    whole function instead of one number.
    """
    lab = s == 1
    if lab.sum() == 0:
        return 0.5
    c = float(np.mean(f_x[lab]))
    return float(np.clip(c, *clip))


@dataclass
class SarEmResult:
    """Fitted pair (f, e) plus the convergence trace.

    ``f``  -- array of ``Pr(y=1|x)`` for the rows given to :func:`sar_em`, at the
              converged iteration.  This is the fault-presence score surface.
    ``e``  -- array of ``Pr(s=1|y=1,x_e)`` for the same rows, times ``kappa``.
    """

    f: np.ndarray
    e: np.ndarray
    c_scar: float
    n_iter: int
    converged: bool
    trace: list[dict] = field(default_factory=list)
    coef_f: np.ndarray | None = None
    coef_e: np.ndarray | None = None
    class_prior: float = float("nan")
    kappa: float = 1.0
    meta: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "n_iter": self.n_iter,
            "converged": self.converged,
            "kappa": self.kappa,
            "c_scar_label_frequency": self.c_scar,
            "e_min": float(np.min(self.e)) if self.e.size else None,
            "e_max": float(np.max(self.e)) if self.e.size else None,
            "e_mean": float(np.mean(self.e)) if self.e.size else None,
            "f_mean": float(np.mean(self.f)) if self.f.size else None,
            "trace": self.trace,
            "meta": self.meta,
        }


def sar_em(X: np.ndarray, s: np.ndarray, Xe: np.ndarray, *,
           d: float = 0.10, kappa: float = 1.0, max_iter: int = 25,
           tol_prop: float = 1e-3, tol_ll: float = 1e-3, C: float = 1.0,
           w_clip: float = W_CLIP, verbose: bool = False) -> SarEmResult:
    """Fit ``(f, e)`` under the SAR assumption by the EM scheme described above.

    Parameters
    ----------
    X   : (n, p) classifier attributes (standardised).
    s   : (n,) selection indicator, 1 = in the catalogue, 0 = unlabelled.
    Xe  : (n, q) **propensity attributes**, a subset of the same information.
    d   : local-certainty parameter.  Rows whose current ``f`` is at least
          ``1 - d`` are treated as *certain* positives when refitting ``e``,
          which is the paper's local-certainty device for anchoring the upper end
          of the propensity scale.
    kappa : scale multiplier on the fitted propensity, for the sensitivity
          analysis demanded by the lane paragraph.

    Returns
    -------
    SarEmResult.

    Notes
    -----
    * Log-likelihood:  ``LL = sum_i [ s_i log(e_i f_i) + (1-s_i) log(1 - e_i f_i) ]``
      which is the likelihood of the observed selection indicator under SAR.
    * Convergence uses the paper's joint criterion: stop when the log likelihood
      has SETTLED (``|LL_k - LL_{k-1}| < tol_ll``) **and** the propensity model
      has settled (``max|e_k - e_{k-1}| < tol_prop``).  Requiring ``LL`` to
      increase monotonically would never terminate here: the M-step used is the
      propensity-weighted ERM of the companion paper, not the exact posterior
      maximiser, so ``LL`` oscillates at the ~0.3 % level (see
      ``evidence/gate.json -> sar_em_trace``).  This is reported, not hidden.
    * Refitting ``e`` uses **only** ``Xe`` (the attribute restriction) and uses
      the E-step posterior as a *weight*, never as a hard label, so the update
      cannot manufacture evidence.
    """
    X = np.asarray(X, dtype=np.float64)
    Xe = np.asarray(Xe, dtype=np.float64)
    s = np.asarray(s).astype(np.int8).reshape(-1)
    if X.shape[0] != s.size or Xe.shape[0] != s.size:
        raise ValueError("X, Xe and s must have the same number of rows")
    n = s.size
    lab = s == 1
    if lab.sum() < 16:
        raise ValueError("SAR-EM needs at least 16 labelled examples")

    # ---- initialisation, exactly as the companion survey section 5.1 says ----
    # classifier: "a balanced model which considers the unlabeled examples as
    # negative"; propensity model: "using the classification model to estimate
    # the probabilities of each unlabeled example being positive".
    base_clf = _fit_logreg(X, s, None, C=C, max_iter=150)
    f = base_clf.predict_proba(X)[:, 1]
    c_scar = elkan_noto_label_frequency(f, s)
    e = np.clip(f, E_MIN, 1.0)  # initial propensity ~ probability of being positive
    e = np.where(lab, np.maximum(e, c_scar), e)
    e = np.clip(e, E_MIN, 1.0) * kappa
    e = np.clip(e, E_MIN, 1.0)

    coef_e = None
    trace: list[dict] = []
    prev_ll = -np.inf
    prev_e = e.copy()
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        # ---------------- E-step: implied positives ----------------
        p_post = np.zeros(n, dtype=np.float64)
        unl = ~lab
        denom = 1.0 - f[unl] * e[unl]
        denom = np.maximum(denom, 1e-12)
        p_post[unl] = (f[unl] * (1.0 - e[unl])) / denom
        p_post[lab] = 1.0
        p_post = np.clip(p_post, 0.0, 1.0)

        # ---------------- M-step 1: propensity-weighted classifier ----------
        from .pu import propensity_weighted_fit  # local import avoids a cycle
        clf_f, f = propensity_weighted_fit(X, s, e, C=C, w_clip=w_clip)

        # ---------------- M-step 2: propensity model -----------------------
        certain = f >= (1.0 - d)
        w_e = np.where(lab, 1.0, p_post)
        w_e = w_e * (1.0 + certain)          # local-certainty weighting
        y_e = np.where(lab | certain, 1, 0)
        if y_e.min() == y_e.max():
            clf_e = None
            e_new = e  # cannot fit; leave the propensity alone
        else:
            clf_e = _fit_logreg(Xe, y_e, w_e, C=C, max_iter=150)
            e_new = np.clip(clf_e.predict_proba(Xe)[:, 1], E_MIN, 1.0)
        e_new = np.clip(e_new * kappa, E_MIN, 1.0)

        # LL = sum_i [ s_i log(e_i f_i) + (1-s_i) log(1 - e_i f_i) ]
        p_sel = np.clip(e_new * f, 1e-300, 1.0 - 1e-12)
        ll = float(np.sum(np.where(lab, np.log(p_sel), np.log1p(-p_sel))))
        d_prop = float(np.max(np.abs(e_new - prev_e))) if e_new.shape == prev_e.shape else np.inf
        ll_settled = abs(ll - prev_ll) < tol_ll
        trace.append({"iter": it, "loglik": ll, "prop_change": d_prop,
                      "p_post_mean": float(p_post[unl].mean()),
                      "certain_fraction": float(certain.mean()),
                      "e_mean": float(e_new.mean()), "f_mean": float(f.mean())})
        if verbose:
            print(f"  SAR-EM it={it:2d} ll={ll:.6f} d_e={d_prop:.5f} "
                  f"p_post={trace[-1]['p_post_mean']:.4f} e_mean={e_new.mean():.4f}")
        if clf_e is not None:
            coef_e = np.asarray(clf_e.beta, np.float64)
        e, prev_e = e_new, e
        prev_ll = ll
        if ll_settled and d_prop < tol_prop:
            converged = True
            break

    return SarEmResult(
        f=np.asarray(f, np.float64), e=np.asarray(e, np.float64),
        c_scar=c_scar, n_iter=it, converged=converged, trace=trace,
        coef_f=getattr(clf_f, "coef_", None), coef_e=coef_e,
        class_prior=float(lab.mean()), kappa=kappa,
        meta={"d": d, "w_clip": w_clip, "C": C, "n": int(n),
              "n_labelled": int(lab.sum()), "n_unlabelled": int((~lab).sum()),
              "propensity_attributes_restricted": True},
    )
