"""Serialize a research surface, validate, audit pre-placement, then fail closed.

No training, no budget search, no dot placement, and no competition upload.
A negative TIFF stays in ignored artifacts/quarantine and is NEVER published.
"""
import _path  # noqa: F401
from gems65.common import ROOT, write_json, sha256, verify_template
from gems65.gate import decide
from gems57.submission_writer import write_submission
from gems57.uniqueness import compare_array_to_registry, summarize_registry_rows, saturation_certificate
from validate_submission import check
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
import numpy as np
import rasterio


def main():
    verify_template()
    experiments=json.loads((ROOT/'evidence/experiments.json').read_text())
    if experiments.get('experiments_completed') != 3 or not experiments.get('canary_ok'):
        raise ValueError('Incomplete experiment evidence; no research TIFF should be built')
    raw_path=ROOT/'data/cache/primary_surface.npy'
    if sha256(raw_path) != experiments['primary_surface_sha256']:
        raise ValueError('OOF surface identity changed')
    p=np.load(raw_path).astype('float32')
    fp=np.load(ROOT/'data/cache/footprint.npy')
    cat=np.load(ROOT/'data/cache/catalogue.npy')
    feature_meta=json.loads((ROOT/'evidence/feature_cache.json').read_text())
    for key in ['footprint','catalogue']:
        if sha256(ROOT/f'data/cache/{key}.npy') != feature_meta[f'{key}_sha256']:
            raise ValueError(f'{key} cache drift')
    if not np.isfinite(p).all() or (p<0).any() or (p>1).any():
        raise ValueError('Model did not produce a normalized finite surface; no repair')
    # Deployment mask only: all catalogue pixels are now visible. It was NOT
    # applied to withheld truth in the holdout evaluation.
    p[~fp|cat]=0
    pixel_digest=hashlib.sha256(p.tobytes()).hexdigest()
    name=f'gems65-sar-em-c050-oof-20261011-{pixel_digest[:12]}-RESEARCH-ONLY'
    note='SAR-EM c=0.50; five mapping covariates; weights capped at 10; OOF continuous. NEGATIVE: DO NOT SUBMIT.'
    path=ROOT/'artifacts/quarantine'/f'{name}.tif'
    if path.exists():
        receipt=json.loads(path.with_suffix('.json').read_text())
        if sha256(path)!=receipt['sha256']:
            raise ValueError('Existing quarantine file changed')
        with rasterio.open(path) as existing:
            pixels=existing.read(1)
        if pixels.shape!=p.shape or not np.array_equal(pixels[fp],p[fp]):
            raise ValueError('Existing quarantine pixels differ from the recorded new model surface')
        del pixels
    else:
        receipt=write_submission(path,p,ROOT/'data/raw/sample_submission.tif',fp,
            catalogue=cat,name=name,note=note,metadata=dict(research_only=True,eligible_for_download=False,
            construction='New fitted SAR-PU OOF surface, no prior raster as model input',
            scientific_gate_already_failed=True,final_dots_created=False))
    validator=check(path,ROOT/'data/raw/sample_submission.tif',ROOT/'data/raw/existing_faults.tif')
    write_json(ROOT/'evidence/validator_output.json',validator)
    pins=json.loads((ROOT/'evidence/audit_raster_pins.json').read_text())
    # Review the explicitly requested incumbent and its base before the known
    # saturated witness. Stop on the FIRST actual duplicate comparison.
    rows=[]; audit=None; stopped=False
    for pin in [pins[1],pins[2],pins[0]]:
        prior=ROOT/pin['local_path']
        if sha256(prior)!=pin['sha256']:
            raise ValueError('Prior raster pin changed')
        idx=dict(rasters=[dict(repo_first=pin['repo'],sources=[pin['path']],
                cache_file=str(prior),sha256=pin['sha256'])],complete_accessible_scan=False,errors=[])
        audit=compare_array_to_registry(p,idx,fp,file_sha256=sha256(path),include_reverse=False)
        row=audit['rows'][0]
        if 'error' not in row:
            with rasterio.open(prior) as ds:
                other=ds.read(1)
            # Explicit agreement is measured only inside the common footprint,
            # so compression/nodata/metadata changes cannot masquerade as novelty.
            row['exact_pixel_agreement_in_footprint']=float(np.mean(p[fp]==other[fp]))
            row['compared_pixels']=int(fp.sum())
            row['prior_git_blob_sha']=pin['git_blob_sha']
        rows.append(row)
        if any(row.get(k,False) for k in ['duplicate_by_rho','duplicate_by_overlap','identical_bytes','identical_decoded_predictions']):
            stopped=True
            break
    registry=json.loads((ROOT/'registry/prior_rasters.json').read_text())
    unique=summarize_registry_rows(rows,registry_rasters_expected=registry['unique_blobs'],
        complete_accessible_scan=False,source_errors=['Stopped at duplicate witness; unvisited registry is NOT cleared. Private/release/history scope not certified.'],
        candidate_meta=dict(my_file=str(path.relative_to(ROOT)),my_dots=int((p>0).sum()),
            candidate_rank_variation=bool(np.ptp(p[fp])>0),candidate_file_sha256=sha256(path),
            candidate_decoded_sha256=pixel_digest),scope=registry['scope'])
    unique.update(stage='surface_before_placement',stop_on_first_duplicate=stopped,
                  final_dot_check='NOT RUN: mandatory pre-placement duplicate stop',
                  all_prior_rasters_checked=False)
    if stopped and rows[-1]['repo']==pins[0]['repo']:
        with rasterio.open(ROOT/'data/raw/sample_submission.tif') as ds:
            grid=(ds.shape,ds.crs,ds.transform)
        unique['saturation_certificate']=saturation_certificate(ROOT/pins[0]['local_path'],fp,cat,expected_grid=grid)
    write_json(ROOT/'evidence/uniqueness.json',unique)
    expanded_path=ROOT/'evidence/expanded_canaries.json'
    expanded=json.loads(expanded_path.read_text()) if expanded_path.exists() else None
    canary_ok=experiments['canary_ok'] is True and expanded is not None and expanded.get('passed') is True
    primary=next(s for s in experiments['scenarios'] if s['primary'])
    optimized=all(d['all_optimizers_success'] and d['em_converged'] for d in primary['diagnostics'])
    gate=decide(primary['overall'],primary['high_tercile'],canary_ok=canary_ok,
        unique=unique['unique'],format_ok=validator['ok'],incumbent_verified=False,
        registry_complete=unique['complete_accessible_scan'],optimization_ok=optimized)
    write_json(ROOT/'evidence/gate.json',gate)
    card=dict(schema='gems65.run-card.v1',created_at=datetime.now(timezone.utc).isoformat(),
        hypothesis='Mapping selection underrepresents low-relief covered basin-margin faults; five-covariate SAR correction may outperform SCAR nnPU.',
        mechanism='Scale-constrained SAR-EM followed by propensity-aware logistic empirical risk; inverse weights capped at 10. Matched nnPU control.',
        non_fault_mimic='Unfaulted alluvial basin margins and volcanic/lithologic contacts.',
        evidence_class='HOLDOUT-DTI',evaluator_version=primary['overall']['evaluator_version'],
        holdout=dict(sar=primary['overall']['scores']['sar'],nnpu=primary['overall']['scores']['nnpu'],
            paired_difference=primary['overall']['paired_differences']['nnpu'],
            high_propensity_tercile=primary['high_tercile'],
            caveat='Finite-iteration, unanchored sensitivity experiment on mapped faults. Not an organizer score or proof about hidden faults.'),
        sensitivity=[dict(assumed_reference_propensity=s['reference_propensity'],
            sar=s['overall']['scores']['sar'],nnpu=s['overall']['scores']['nnpu']) for s in experiments['scenarios']],
        canary=dict(passed=canary_ok,max_bidirectional_auc=max(
                    max(r['max_direction_auc'] for r in experiments['canaries']),
                    expanded['max_bidirectional_auc'] if expanded else 1.),
                    feature_fold_checks=len(experiments['canaries']),
                    expanded_basis_checks=expanded['checks'] if expanded else 0,
                    expanded_audit_after_fitting=True,evidence_class='LEAKAGE-CANARY-NOT-DTI'),
        em_converged=all(d['em_converged'] for d in primary['diagnostics']),independent_propensity_anchor=None,propensity_identifiable=False,
        registry=dict(stage='surface_before_placement',raster_count_checked=unique['registry_rasters_checked'],
            indexed_blobs=registry['unique_blobs'],complete=False,
            max_rank_correlation=unique['worst_spearman_full_footprint'],max_forward_overlap_3px=unique['worst_dot_overlap'],
            byte_unique_among_checked=unique['byte_unique_among_checked'],pixel_unique_among_checked=unique['pixel_unique_among_checked'],
            literal_gate_passed=False,final_dots_check='not_run_mandatory_stop'),
        raster_sha256=sha256(path),raster_kind='new research-only OOF continuous GeoTIFF, quarantined; NOT a promoted submission',
        validator=dict(status=validator['status'],
            no_nan_inside_footprint=validator['local']['checks'].get('in_footprint_all_finite') is True,
            values_in_0_1=validator['local']['checks'].get('in_footprint_range_0_1') is True,
            crs_shape_transform_match=all(validator['local']['checks'].get(k) is True for k in
                ['crs_epsg_32611','dimensions_3730x3292','transform_matches_sample_submission']),
            outside_footprint_nan=validator['local']['checks'].get('outside_footprint_nan') is True,
            report='validator_output.json',organizer_acceptance=False),
        submission_name=name,note=note,note_characters=len(note),
        verdict=gate['verdict'],eligible_for_download=gate['eligible_for_download'],
        approved_for_weekly_slot=False,submission_slots_used=0,experiments_completed=3,
        reasons=gate['reasons'],next_session=['Independent completeness evidence or a wider identified sensitivity study.',
          'Pre-register convergence criteria/iteration budget before a fresh holdout; do not treat this finite-iteration negative as a theorem about SAR.',
          'Owner/selector must explicitly resolve dense-prior support semantics; no silent uniqueness exemption.',
          'Obtain organizer score receipts, comparable incumbent folds and the current weekly cap.'])
    if card['verdict']!='negative':
        raise AssertionError('This finalize command only publishes negative research cards, not slot candidates')
    write_json(ROOT/'evidence/run_card.json',card)
    print(json.dumps(dict(verdict=gate['verdict'],eligible_for_download=False,raster_sha256=card['raster_sha256'],
                         validator=validator['status'],registry=card['registry'],reasons=gate['reasons']),indent=2))

if __name__=='__main__':main()
