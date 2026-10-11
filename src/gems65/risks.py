"""Risk functions and the small neural classifier used by the SAR-PU lane.

Two arms, identical architecture / folds / data / seed:

``arm="sar"``
    the propensity-aware empirical risk of Bekker, Robberechts & Davis
    (arXiv:1809.03207) for **selected-at-random** (SAR) positive-unlabeled data,
    with the inverse-propensity weights clipped at ``W_CLIP = 10`` as the brief
    requires.

``arm="nnpu"``
    the non-negative PU risk of Kiryo et al. (NeurIPS 2017), i.e. the SCAR
    baseline: it assumes the labelled positives are a *completely* at random
    sample of the positives.

Derivation of the SAR risk (written out so it can be checked, not cited)
----------------------------------------------------------------------
Let ``y`` be the class, ``s`` the label indicator, ``g(x) = P(y=1|x)``,
``e(x) = P(s=1 | y=1, x)`` and ``rho = P(s=1) = E_x[g(x) e(x)]`` -- the
*observable* labelled fraction of the population (``n_L / n``).  Only positives
can be labelled, so ``P(s=1|x) = g(x) e(x)`` and ``p(x|s=1) = g e p / rho``.
Write ``l1(x) = loss(f(x),1)``, ``l0(x) = loss(f(x),0)`` and

    A* = E_x[g l1],   B = E_x[l0],   C* = E_x[g l0].

The target risk is ``R(f) = A* + B - C*``.  Three identities, each obtained by
writing an expectation over an observed subpopulation:

    A*            = rho   * E_{x|s=1}[ l1 / e ]
    E_x[g(1-e)l0] = rho   * E_{x|s=1}[ ((1-e)/e) l0 ]
    (1-rho) E_{x|s=0}[l0] = B - E_x[g e l0]

Combining: ``R = rho*E_{s=1}[l1/e] + (1-rho)*E_{s=0}[l0] - E_x[g(1-e)l0]`` and
``E_x[g(1-e)l0] = rho * E_{x|s=1}[((1-e)/e) l0]``, hence

    R(f) = rho * (1/nL) * sum_L [ l1_i/e_i - ((1-e_i)/e_i) * l0_i ]
           + (1 - rho) * (1/nU) * sum_U l0_j                            (2)

``rho`` needs no unobservable quantity: it is the labelled share of the
population.  Setting ``e(x) = e0`` constant gives ``rho = pi*e0`` and (2)
collapses to ``pi*mean_L(l1) + (1-pi*e0)*mean_U(l0) - pi*(1-e0)*mean_L(l0)``,
which the SCAR population identities reduce to ``pi*A + (1-pi)*B`` -- the true
risk.  ``tests/test_risks.py`` checks both the general SAR case and the SCAR
reduction by Monte Carlo against a known data-generating process.

.. note:: An earlier draft of this module normalised the labelled block by
   ``pi * ebar`` with ``ebar = E_x[e(x)]``.  That is only correct when ``g`` and
   ``e`` are uncorrelated, which is false by construction in this lane (the
   propensity is *high* exactly where faults are dense).  Caught by
   ``test_sar_risk_unbiased_no_clipping``; the correct normaliser ``rho`` is
   recorded here so the mistake cannot come back.

Clipping
--------
``w_i = min(1/e_i, W_CLIP)`` and ``v_i = min((1-e_i)/e_i, W_CLIP)``.  Clipping
is a bias-variance trade: it biases the risk estimate towards under-weighting
low-propensity positives (exactly the environments the lane is trying to
recover) in exchange for a bounded variance.  The fraction of labelled pixels
that are clipped is reported in every receipt so the size of that bias is
visible, never hidden.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

W_CLIP = 10.0


# ---------------------------------------------------------------------------
# losses
# ---------------------------------------------------------------------------
def sigmoid(z: np.ndarray) -> np.ndarray:
    return np.where(z >= 0, 1.0 / (1.0 + np.exp(-z)), np.exp(z) / (1.0 + np.exp(z)))


def softplus(z: np.ndarray) -> np.ndarray:
    """Numerically stable ``log(1+exp(z))``; loss of label 0 at logit ``z``."""
    return np.where(z > 30, z, np.log1p(np.exp(np.clip(z, -60, 30))))


def loss_l1(z: np.ndarray) -> np.ndarray:
    """``-log sigmoid(z)`` = loss(f, 1)."""
    return softplus(-z)


def loss_l0(z: np.ndarray) -> np.ndarray:
    """``-log(1-sigmoid(z))`` = loss(f, 0)."""
    return softplus(z)


# ---------------------------------------------------------------------------
# risk estimators on logits (used both for training and for the receipts)
# ---------------------------------------------------------------------------
def sar_risk(z_lab: np.ndarray, z_unl: np.ndarray, e_lab: np.ndarray, rho: float,
             clip: float = W_CLIP) -> dict:
    """Equation (2).

    ``rho`` is the labelled share of the population, ``P(s=1) = n_L / n`` (full
    counts, *not* the counts of any subsample), and ``e_lab`` are the propensities
    at the labelled pixels.
    """
    if not 0.0 < rho < 1.0:
        raise ValueError(f"rho = P(s=1) must be in (0,1), got {rho}")
    e = np.clip(e_lab, 1e-6, 1.0)
    w = np.minimum(1.0 / e, clip)
    v = np.minimum((1.0 - e) / e, clip)
    lab = rho * np.mean(w * loss_l1(z_lab) - v * loss_l0(z_lab))
    unl = (1.0 - rho) * np.mean(loss_l0(z_unl))
    return dict(risk=float(lab + unl), labelled_term=float(lab), unlabelled_term=float(unl),
                rho=float(rho),
                frac_clipped_w=float(np.mean(1.0 / e > clip)),
                frac_clipped_v=float(np.mean((1.0 - e) / e > clip)),
                w_mean=float(w.mean()), w_max=float(w.max()))


def nnpu_risk(z_lab: np.ndarray, z_unl: np.ndarray, pi: float, gamma: float = 1.0) -> dict:
    """Kiryo et al. (2017) non-negative PU risk, as published."""
    pos = pi * np.mean(loss_l1(z_lab))
    neg_raw = np.mean(loss_l0(z_unl)) - pi * np.mean(loss_l0(z_lab))
    if neg_raw < 0:
        return dict(risk=float(pos - gamma * neg_raw), negative_term=float(neg_raw),
                    non_negative_active=True)
    return dict(risk=float(pos + neg_raw), negative_term=float(neg_raw),
                non_negative_active=False)


# ---------------------------------------------------------------------------
# classifier: one-hidden-layer MLP with exact analytic gradients
# ---------------------------------------------------------------------------
@dataclass
class MLP:
    """``z = relu(X W1 + b1) W2 + b2`` trained by Adam on an explicit risk.

    Small and deterministic: the lane's covariate set has 5-8 channels, so a
    64-unit hidden layer is more than enough and keeps every run reproducible
    from the seed alone.  No framework dependency, no GPU.
    """
    n_in: int
    n_hidden: int = 64
    seed: int = 0
    W1: np.ndarray = field(init=False)
    b1: np.ndarray = field(init=False)
    W2: np.ndarray = field(init=False)
    b2: np.ndarray = field(init=False)

    def __post_init__(self):
        rng = np.random.default_rng(self.seed)
        s1 = np.sqrt(2.0 / self.n_in)
        self.W1 = rng.normal(0.0, s1, (self.n_in, self.n_hidden))
        self.b1 = np.zeros(self.n_hidden)
        self.W2 = rng.normal(0.0, np.sqrt(2.0 / self.n_hidden), (self.n_hidden, 1))
        self.b2 = np.zeros(1)

    def logits(self, X: np.ndarray) -> np.ndarray:
        h = np.maximum(X @ self.W1 + self.b1, 0.0)
        return (h @ self.W2 + self.b2).ravel()

    def prob(self, X: np.ndarray) -> np.ndarray:
        return sigmoid(self.logits(X))

    def _forward(self, X):
        pre = X @ self.W1 + self.b1
        h = np.maximum(pre, 0.0)
        z = (h @ self.W2 + self.b2).ravel()
        return pre, h, z

    def _backward(self, X, pre, h, dz):
        n = X.shape[0]
        gW2 = (h.T @ dz.reshape(-1, 1)) / n
        gb2 = np.array([dz.mean()])
        dh = (dz.reshape(-1, 1) @ self.W2.T) * (pre > 0)
        gW1 = (X.T @ dh) / n
        gb1 = dh.mean(axis=0)
        return gW1, gb1, gW2, gb2

    def _step(self, grads, state, lr, b1=0.9, b2=0.999, eps=1e-8):
        names = ("W1", "b1", "W2", "b2")
        for name, g in zip(names, grads):
            m, v = state[name]
            m *= b1; m += (1 - b1) * g
            v *= b2; v += (1 - b2) * g * g
            state[name] = (m, v)
            mh = m / (1 - b1 ** state["t"])
            vh = v / (1 - b2 ** state["t"])
            setattr(self, name, getattr(self, name) - lr * mh / (np.sqrt(vh) + eps))
        state["t"] += 1


def _dz_sar(z_lab, z_unl, e_lab, rho, clip):
    """d(R)/dz for equation (2), per sample."""
    e = np.clip(e_lab, 1e-6, 1.0)
    w = np.minimum(1.0 / e, clip)
    v = np.minimum((1.0 - e) / e, clip)
    p_lab = sigmoid(z_lab)
    # d l1/dz = -(1-p);  d l0/dz = p
    dz_lab = rho * (w * (-(1.0 - p_lab)) - v * p_lab) / z_lab.size
    dz_unl = (1.0 - rho) * sigmoid(z_unl) / z_unl.size
    return dz_lab, dz_unl


def _dz_nnpu(z_lab, z_unl, pi, gamma=1.0):
    neg_raw = np.mean(loss_l0(z_unl)) - pi * np.mean(loss_l0(z_lab))
    p_lab = sigmoid(z_lab)
    p_unl = sigmoid(z_unl)
    dz_lab = pi * (-(1.0 - p_lab)) / z_lab.size
    if neg_raw < 0:
        dz_lab = dz_lab - gamma * (-pi * p_lab / z_lab.size)
        dz_unl = np.zeros_like(z_unl)
    else:
        dz_lab = dz_lab - pi * p_lab / z_lab.size
        dz_unl = p_unl / z_unl.size
    return dz_lab, dz_unl


def train(model: MLP, X_lab: np.ndarray, X_unl: np.ndarray, *, arm: str,
          rho: float, pi: float, e_lab: np.ndarray | None = None,
          epochs: int = 300, lr: float = 3e-2, batch: int = 4096,
          clip: float = W_CLIP, gamma: float = 1.0, seed: int = 0,
          trace_every: int = 0) -> dict:
    """Mini-batch Adam on the chosen risk.  Identical inputs for both arms.

    ``rho`` = P(s=1), the labelled share of the *population* (full counts, not
    the subsample) -- the normaliser of equation (2).  ``pi`` = P(y=1), the class
    prior estimated by the EM, which only the nnPU baseline needs.
    """
    if arm not in ("sar", "nnpu"):
        raise ValueError("arm must be 'sar' or 'nnpu'")
    if arm == "sar" and e_lab is None:
        raise ValueError("the SAR arm requires propensities at the labelled pixels")
    rng = np.random.default_rng(seed + 1)
    state = {"W1": (np.zeros_like(model.W1), np.zeros_like(model.W1)),
             "b1": (np.zeros_like(model.b1), np.zeros_like(model.b1)),
             "W2": (np.zeros_like(model.W2), np.zeros_like(model.W2)),
             "b2": (np.zeros_like(model.b2), np.zeros_like(model.b2)), "t": 1}
    n_lab, n_unl = X_lab.shape[0], X_unl.shape[0]
    per_epoch = max(1, int(np.ceil(max(n_lab, n_unl) / batch)))
    history = []
    for ep in range(epochs):
        il = rng.integers(0, n_lab, per_epoch * batch)
        iu = rng.integers(0, n_unl, per_epoch * batch)
        for b in range(per_epoch):
            sl, su = il[b * batch:(b + 1) * batch], iu[b * batch:(b + 1) * batch]
            Xl, Xu = X_lab[sl], X_unl[su]
            pre_l, h_l, z_l = model._forward(Xl)
            pre_u, h_u, z_u = model._forward(Xu)
            if arm == "sar":
                dz_l, dz_u = _dz_sar(z_l, z_u, e_lab[sl], rho, clip)
            else:
                dz_l, dz_u = _dz_nnpu(z_l, z_u, pi, gamma)
            # scale to the batch: _backward divides by batch size
            gl = model._backward(Xl, pre_l, h_l, dz_l * z_l.size)
            gu = model._backward(Xu, pre_u, h_u, dz_u * z_u.size)
            model._step(tuple(a + b_ for a, b_ in zip(gl, gu)), state, lr)
        if trace_every and (ep % trace_every == 0 or ep == epochs - 1):
            z_l = model.logits(X_lab[:20000])
            z_u = model.logits(X_unl[:20000])
            r = (sar_risk(z_l, z_u, e_lab[:20000], rho, clip) if arm == "sar"
                 else nnpu_risk(z_l, z_u, pi, gamma))
            history.append({"epoch": ep, **r})
    return dict(arm=arm, epochs=epochs, lr=lr, batch=batch, clip=clip, rho=float(rho),
                pi=float(pi), n_labelled=int(n_lab), n_unlabelled=int(n_unl),
                history=history)
