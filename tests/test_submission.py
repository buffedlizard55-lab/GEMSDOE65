import json
import zipfile
import subprocess
import sys
from pathlib import Path
import numpy as np
import pytest
import rasterio
from gems65.common import ROOT
from gems57 import grid
from gems57.submission_writer import write_submission
from gems57.gates import format_report
from validate_submission import check


@pytest.fixture(scope='module')
def fixture_grid(tmp_path_factory):
    folder=tmp_path_factory.mktemp('format')
    fp=np.zeros(grid.SHAPE,bool);fp[100:106,100:106]=1
    p=np.zeros(grid.SHAPE,'float32');p[102,102]=.7
    sample=np.full(grid.SHAPE,np.nan,'float32');sample[fp]=0
    path=folder/'sample.tif'
    with rasterio.open(path,'w',driver='GTiff',width=grid.WIDTH,height=grid.HEIGHT,count=1,
        dtype='float32',crs='EPSG:32611',transform=grid.TRANSFORM,nodata=np.nan,compress='deflate') as ds:
        ds.write(sample,1)
    return folder,fp,p,path


def test_writer_actual_tiff_and_single_member_zip_roundtrip(fixture_grid):
    folder,fp,p,sample=fixture_grid;dest=folder/'safe.tif'
    receipt=write_submission(dest,p,sample,fp,name='unit-test-only',note='Synthetic format fixture, not model output.')
    with rasterio.open(dest) as s:
        decoded=s.read(1)
        assert s.count==1 and s.dtypes[0]=='float32' and s.crs.to_epsg()==32611
        assert s.shape==grid.SHAPE and s.transform==grid.TRANSFORM
        np.testing.assert_array_equal(decoded[fp],p[fp])
        assert np.isnan(decoded[~fp]).all()
    assert check(dest,sample)['ok']
    assert not receipt['approved_for_weekly_slot']
    with zipfile.ZipFile(dest.with_suffix('.zip')) as z:
        assert z.namelist()==['safe.tif']
        assert z.read('safe.tif')==dest.read_bytes()
    with pytest.raises(FileExistsError):write_submission(dest,p,sample,fp,name='test',note='test')


@pytest.mark.parametrize('value',[-9999.,-.001,1.01,np.inf,np.nan])
def test_writer_refuses_invalid_values_without_creating_a_file(fixture_grid,value):
    folder,fp,p,sample=fixture_grid
    bad=p.copy();bad[102,102]=value;dest=folder/f'bad-{value}.tif'
    with pytest.raises(ValueError):write_submission(dest,bad,sample,fp,name='test',note='test')
    assert not dest.exists() and not dest.with_suffix('.zip').exists()


def test_no_positive_outside_or_on_known_fault(fixture_grid):
    folder,fp,p,sample=fixture_grid
    bad=p.copy();bad[2,2]=.1
    with pytest.raises(ValueError):write_submission(folder/'outside.tif',bad,sample,fp,name='test',note='test')
    catalogue=p>0
    with pytest.raises(ValueError):write_submission(folder/'catalogue.tif',p,sample,fp,name='test',note='test',catalogue=catalogue)


def test_note_limit(fixture_grid):
    folder,fp,p,sample=fixture_grid
    with pytest.raises(ValueError):write_submission(folder/'note.tif',p,sample,fp,name='test',note='n'*141)


def test_range_and_grid_error_detected_from_serialized_bytes(fixture_grid):
    folder,fp,p,sample=fixture_grid
    path=folder/'wrong.tif';a=np.full((4,5),-9999,'float32')
    with rasterio.open(path,'w',driver='GTiff',height=4,width=5,count=1,dtype='float32',
        transform=rasterio.Affine(100,0,1,0,-100,1),crs='EPSG:4326') as ds:ds.write(a,1)
    report=format_report(path,sample,footprint=fp)
    assert not report['ok']
    assert any('crs' in str(p).lower() or 'epsg' in str(p).lower() for p in report['problems'])


def test_cli_fails_for_missing_file():
    r=subprocess.run([sys.executable,str(ROOT/'scripts/validate_submission.py'),'file-does-not-exist.tif'],
                     capture_output=True,text=True)
    assert r.returncode!=0
    assert json.loads(r.stdout)['status']=='FAIL'
