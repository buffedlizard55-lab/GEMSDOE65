from pathlib import Path
import pytest
import build_site
from check_site import check_site


def test_site_links_and_no_download_for_negative():
    assert check_site()['ok'],check_site()['errors']


@pytest.mark.parametrize('extension',['.tif','.TIFF','.zip','.npy','.npz'])
def test_unlinked_negative_artifact_also_blocks(tmp_path,monkeypatch,extension):
    monkeypatch.setattr(build_site,'DOCS',tmp_path)
    (tmp_path/('secret'+extension)).write_bytes(b'not published')
    with pytest.raises(ValueError):build_site.assert_no_public_rasters()


def test_symlink_cannot_expose_quarantine(tmp_path,monkeypatch):
    public=tmp_path/'docs';public.mkdir();secret=tmp_path/'secret';secret.write_bytes(b'tiff')
    (public/'image.dat').symlink_to(secret)
    monkeypatch.setattr(build_site,'DOCS',public)
    with pytest.raises(ValueError):build_site.assert_no_public_rasters()
