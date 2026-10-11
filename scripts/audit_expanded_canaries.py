"""Pass-2 diagnostic only: no model fitting, no placements, no new experiment."""
import _path  # noqa: F401
from gems65.common import ROOT, write_json, sha256
from gems65.canary import feature_canaries
from gems57 import spatial
from run_experiments import sample_training
import numpy as np
import json


def main():
    cache=ROOT/'data/cache'
    bank=np.load(cache/'features.npy',mmap_mode='r');fp=np.load(cache/'footprint.npy');cat=np.load(cache/'catalogue.npy')
    original=json.loads((ROOT/'evidence/experiments.json').read_text())
    metadata=json.loads((ROOT/'evidence/feature_cache.json').read_text())
    if sha256(cache/'features.npy')!=metadata['feature_bank_sha256']:raise ValueError('Cache drift')
    names=[f['name'] for f in metadata['features']]
    rows=[]
    for fold in spatial.folds(cat,fp,buffer_px=80):
        f=fold['fold'];x,s,w,sampling=sample_training(fold,cat,bank,651100+f)
        if sampling['sample_indices_sha256']!=original['folds'][f]['sampling']['sample_indices_sha256']:
            raise ValueError('Sampling not identical to actual experiment')
        ids=np.flatnonzero(fold['region'].ravel())
        rows.extend(feature_canaries(x,w,bank,ids,fold['truth'].ravel()[ids],names,f))
    report=dict(evidence_class='LEAKAGE-CANARY-NOT-DTI',stage='Pass-2 expanded-basis audit after the already-negative fits',
        no_model_refit=True,new_geological_experiments=0,checks=len(rows),passed=all(x['passed'] for x in rows),
        max_bidirectional_auc=max(x['max_direction_auc'] for x in rows),rows=rows,
        change='Future runner checks every standardized/quadratic basis before fitting; original raw-feature checks retained.')
    write_json(ROOT/'evidence/expanded_canaries.json',report)
    print('Expanded canary checks:',report['checks'],'passed:',report['passed'],'max:',report['max_bidirectional_auc'])

if __name__=='__main__':main()
