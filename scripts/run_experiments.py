"""One preregistered SAR-PU mechanism, three scale-sensitivity experiments.

Reads no prior prediction. Continuous holdout evaluation precedes placement.
All states/evidence are on disk, CPU-only, bounded to the supplied experiment cap.
"""
import _path  # noqa: F401
from gems65.common import ROOT, verify_template, write_json, sha256
from gems65.pu import fit_sar, predict, weighted_quantile
from gems57 import spatial, evaluate_holdout
import numpy as np
from gems65.canary import feature_canaries
from datetime import datetime, timezone
import time
import json
import gc


def sample_training(fold, catalogue, bank, seed, npos=6000, nunl=30000):
    train = fold['train']
    pos = np.flatnonzero((train & fold['visible']).ravel())
    unl = np.flatnonzero((train & ~catalogue).ravel())
    # Whole hidden components and the spatial buffer never enter either sample.
    if not len(pos) or not len(unl):
        raise ValueError('Training fold has an empty sampling stratum')
    rng = np.random.default_rng(seed)
    ip = rng.choice(pos, min(npos, len(pos)), replace=False)
    iu = rng.choice(unl, min(nunl, len(unl)), replace=False)
    ids = np.r_[ip, iu]
    mu = len(pos) / (len(pos) + len(unl))
    s = np.r_[np.ones(len(ip)), np.zeros(len(iu))]
    weights = np.r_[np.full(len(ip), mu / len(ip)), np.full(len(iu), (1 - mu) / len(iu))]
    x = bank.reshape(len(bank), -1)[:, ids].T.copy()
    return x, s, weights, dict(n_positive_population=len(pos), n_unlabeled_population=len(unl),
                             n_positive_sample=len(ip), n_unlabeled_sample=len(iu),
                             sample_indices_sha256=__import__('hashlib').sha256(ids.tobytes()).hexdigest())


def main():
    begin = time.monotonic()
    verify_template()
    report_path = ROOT / 'evidence/experiments.json'
    if report_path.exists():
        raise FileExistsError('Preregistered experiments already recorded; do not silently rerun the holdout.')
    fp = np.load(ROOT / 'data/cache/footprint.npy')
    cat = np.load(ROOT / 'data/cache/catalogue.npy')
    bank = np.load(ROOT / 'data/cache/features.npy', mmap_mode='r')
    cache_meta = json.loads((ROOT / 'evidence/feature_cache.json').read_text())
    if sha256(ROOT / 'data/cache/features.npy') != cache_meta['feature_bank_sha256']:
        raise ValueError('Feature cache drift')
    for key in ['footprint','catalogue']:
        if sha256(ROOT / f'data/cache/{key}.npy') != cache_meta[f'{key}_sha256']:
            raise ValueError(f'{key} cache drift')
    names = [a['name'] for a in cache_meta['features']]
    scenarios = [.5, .25, .75]
    nblocks = ((fp.shape[0] + 199) // 200) * ((fp.shape[1] + 199) // 200)
    terms = {c:{stratum:{arm:np.zeros((nblocks,4)) for arm in ['sar','nnpu']}
                for stratum in ['overall','high_tercile']} for c in scenarios}
    results = dict(started_at=datetime.now(timezone.utc).isoformat(), lane='selection-bias-aware SAR-PU',
                   experiments_planned=3, scenarios=[], canaries=[], folds=[],
                   target='mapped-fault hide-and-recover, NOT geothermal vents or organizer hidden faults',
                   placement_performed=False, submission_slots_used=0)
    diagnostics = {c:[] for c in scenarios}
    oof = np.lib.format.open_memmap(ROOT / 'data/cache/primary_surface.npy', mode='w+', dtype='float32', shape=fp.shape)
    oof[:] = 0.
    for fold in spatial.folds(cat, fp, buffer_px=80):
        f = fold['fold']; print('FOLD', f, fold['receipt'], flush=True)
        results['folds'].append(fold['receipt'])
        x, s, weights, sampling = sample_training(fold, cat, bank, 651100 + f)
        results['folds'][-1]['sampling'] = sampling
        # Every raw feature is tested alone before fitting any joint model on this fold.
        ids = np.flatnonzero(fold['region'].ravel())
        truth = fold['truth'].ravel()[ids]
        canaries = feature_canaries(x, weights, bank, ids, truth, names, f)
        results['canaries'].extend(canaries)
        if not all(row['passed'] for row in canaries):
            results.update(stopped='leakage_canary', verdict='negative')
            write_json(report_path, results)
            return
        ys,xs = np.nonzero(fold['region'])
        sl = np.s_[max(0,ys.min()-3):min(fp.shape[0],ys.max()+4), max(0,xs.min()-3):min(fp.shape[1],xs.max()+4)]
        origin = (sl[0].start, sl[1].start)
        crop_fold = {k:fold[k][sl] for k in ['region','visible','truth']}
        for c in scenarios:
            if time.monotonic()-begin > 5400:
                results.update(stopped='time_budget', verdict='negative')
                write_json(report_path, results)
                return
            print('FIT',f,c,flush=True)
            model = fit_sar(x,s,weights,reference_propensity=c)
            diag = model['diagnostics']; diag.update(fold=f, sampling=sampling)
            diagnostics[c].append(diag)
            train_e = predict(model, x)['propensity']
            threshold = weighted_quantile(train_e, weights, 2/3)
            diag['high_tercile_threshold'] = threshold
            pred = {arm:np.zeros(crop_fold['region'].shape, 'float32') for arm in ['sar','nnpu','propensity']}
            # Match local coordinates to the full fixed evaluation region; fit transforms on train only.
            row,col = np.unravel_index(ids,fp.shape)
            local_ids = (row-origin[0])*pred['sar'].shape[1] + col-origin[1]
            for start in range(0,len(ids),100000):
                chunk = ids[start:start+100000]
                xx = bank.reshape(len(bank),-1)[:,chunk].T
                out = predict(model,xx)
                for arm in pred:
                    pred[arm].ravel()[local_ids[start:start+100000]] = out[arm]
            high = pred['propensity'] >= threshold
            for stratum,valid in [('overall',fp[sl]),('high_tercile',fp[sl]&high)]:
                for arm in ['sar','nnpu']:
                    _,tt = evaluate_holdout.evaluate(pred[arm], crop_fold, valid, origin=origin,global_shape=fp.shape)
                    terms[c][stratum][arm] += tt
            if c == .5:
                oof[sl] += pred['sar']
            print('DONE',f,c,'EM',diag['em_iterations'],'converged',diag['em_converged'],flush=True)
            del pred,model
            gc.collect()
        write_json(ROOT / 'evidence/experiment_progress.json', results)
        del fold,x,s,weights,truth,ids
        gc.collect()
    oof.flush()
    for c in scenarios:
        scenarios_out = dict(reference_propensity=c, primary=c==.5, diagnostics=diagnostics[c])
        for stratum in ['overall','high_tercile']:
            scenarios_out[stratum] = evaluate_holdout.pooled_summary(terms[c][stratum], draws=1000,seed=651011,candidate='sar')
        results['scenarios'].append(scenarios_out)
    results.update(completed_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-begin,
                   experiments_completed=len(scenarios), canary_ok=True,
                   primary_surface_sha256=sha256(ROOT / 'data/cache/primary_surface.npy'),
                   surface_kind='OOF continuous sensitivity surface; not a deployment raster',
                   verdict='pending_registry_and_gate')
    write_json(report_path, results)
    for r in results['scenarios']:
        print(r['reference_propensity'],json.dumps(r['overall']['scores']),flush=True)

if __name__ == '__main__':
    main()
