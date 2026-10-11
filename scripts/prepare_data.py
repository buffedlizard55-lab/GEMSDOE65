"""Reuse the pinned feature stack and existing cached topo/lidar products.

Only the five declared propensity covariates and physical outcome bands are
extracted. No full-catalogue-derived feature, prior submission, or sample value
is read as a predictor. Footprint is the template's finite mask, not band-1 mask.
"""
import _path  # noqa: F401
from gems65.common import ROOT, sha256, write_json
import json
import numpy as np
import rasterio
from scipy import ndimage as ndi

NAMES = ['local_relief', 'slope', 'gravity_basin_proxy', 'lidar_coverage', 'distance_to_terrain_front',
         'magnetic_horizontal_gradient', 'gravity_horizontal_gradient', 'gravity_vertical_gradient',
         'detrended_elevation', 'detrended_slope', 'basement_surface', 'conductivity']


def main():
    from restore_data import main as restore
    restore()
    cache = ROOT / 'data/cache'
    cache.mkdir(parents=True, exist_ok=True)
    sample = ROOT / 'data/raw/sample_submission.tif'
    with rasterio.open(sample) as s:
        fp = np.isfinite(s.read(1))
        shape, transform, crs = s.shape, s.transform, s.crs
    with rasterio.open(ROOT / 'data/raw/existing_faults.tif') as s:
        if s.shape != shape or s.crs != crs or s.transform != transform:
            raise ValueError(f'Input grid mismatch: {s.name}')
        cat = (s.read(1) == 1) & fp
    np.save(cache / 'footprint.npy', fp)
    np.save(cache / 'catalogue.npy', cat)
    bank = np.lib.format.open_memmap(cache / 'features.npy', mode='w+', dtype='float32', shape=(len(NAMES), *shape))
    topo_manifest = json.loads((ROOT / 'registry/topography_cache_manifest.json').read_text())
    with rasterio.open(ROOT / 'data/external/topo_10m_derived_100m_u8.tif') as s:
        if s.shape != shape or s.crs != crs or s.transform != transform:
            raise ValueError(f'Input grid mismatch: {s.name}')
        for output, band in [(0, 5), (1, 1)]:
            q = s.read(band)
            pin = topo_manifest['bands'][band - 1]
            a = pin['lo'] + (q.astype('float32') - 1) / 254 * (pin['hi'] - pin['lo'])
            a[(q == 0) | ~fp] = np.nan
            bank[output] = a
    with rasterio.open(ROOT / 'data/raw/training_features.tif') as s:
        if s.shape != shape or s.crs != crs or s.transform != transform:
            raise ValueError(f'Input grid mismatch: {s.name}')
        for out, band in [(2, 13), (5, 3), (6, 18), (7, 11), (8, 12), (9, 19), (10, 15), (11, 17)]:
            a = s.read(band).astype('float32')
            a[(s.read_masks(band) == 0) | ~fp | ~np.isfinite(a)] = np.nan
            bank[out] = -a if out == 2 else a
    with rasterio.open(ROOT / 'data/external/lidar_scarp_features_u8.tif') as s:
        if s.shape != shape or s.crs != crs or s.transform != transform:
            raise ValueError(f'Input grid mismatch: {s.name}')
        if s.descriptions[11] != 'valid':
            raise ValueError('Coverage band identity changed')
        coverage = (s.read(12) > 0).astype('float32')
        coverage[~fp] = np.nan
        bank[3] = coverage
    # Observable terrain proxy; NOT distance to a mapped fault or an official range-front map.
    steep = fp & (bank[1] >= 8.0) & (bank[0] >= 10.0)
    front = steep & ~ndi.binary_erosion(steep, structure=np.ones((3, 3), bool))
    if not front.any():
        raise ValueError('No terrain-front proxy found')
    dist = np.log1p(ndi.distance_transform_edt(~front) * 100).astype('float32')
    dist[~fp] = np.nan
    bank[4] = dist
    bank.flush()
    report = dict(evidence_class='DATA-MEASUREMENT', shape=list(shape), crs=str(crs), transform=list(transform)[:6],
        footprint_pixels=int(fp.sum()), catalogue_pixels=int(cat.sum()), feature_bank_sha256=sha256(cache / 'features.npy'),
        footprint_sha256=sha256(cache / 'footprint.npy'), catalogue_sha256=sha256(cache / 'catalogue.npy'),
        source_stack_sha256=sha256(ROOT / 'data/raw/training_features.tif'),
        independent_mapping_anchor=None, propensity_scale_identifiable=False,
        features=[dict(name=n, propensity=i < 5, catalogue_derived=False,
                       missing_in_footprint=int((fp & ~np.isfinite(bank[i])).sum())) for i, n in enumerate(NAMES)],
        caveats=['Negative isostatic gravity is only a basin-fill proxy, not an inversion.',
                 'Terrain-front distance is derived from independent slope/relief thresholds, not verified range-front faults.',
                 'Lidar coverage is validity in the cached derivative, not an official complete acquisition index.',
                 'Hash consistency does not prove official provenance.'])
    write_json(ROOT / 'evidence/feature_cache.json', report)
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
