"""Feature-only leakage diagnostics, including every actual polynomial basis."""
import numpy as np
from sklearn.metrics import roc_auc_score
from .pu import Design


def feature_canaries(training, weights, bank, ids, truth, names, fold):
    design=Design.fit(training,weights)
    rows=[]
    if len(names)!=len(bank) or len(ids)!=len(truth) or not np.any(truth) or np.all(truth):
        raise ValueError('Canary requires matching features and both label classes')
    for j,name in enumerate(names):
        raw=bank[j].ravel()[ids].astype('float64')
        raw[~np.isfinite(raw)]=design.med[j]
        z=np.clip((raw-design.med[j])/design.scale[j],-6,6)
        for transform,values in [('imputed_raw',raw),('standardized_clipped',z),('quadratic_basis',.25*z*z)]:
            auc=float(roc_auc_score(truth,values))
            rows.append(dict(evidence_class='LEAKAGE-CANARY-NOT-DTI',fold=fold,feature=name,
                transform=transform,auc=auc,max_direction_auc=max(auc,1-auc),
                withheld_positive_pixels=int(np.sum(truth)),
                negatives='catalogue-zero proxies, not verified absence',passed=max(auc,1-auc)<=.9))
    return rows
