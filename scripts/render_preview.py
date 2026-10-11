"""Render an illustrative, explicitly stretched map from the quarantined TIFF.

Optional diagnostic; never changes predictions. Requires a locally generated
research TIFF. No old submission or synthetic geology is used.
"""
import _path  # noqa: F401
from gems65.common import ROOT, sha256, write_json
from PIL import Image, ImageDraw
import json
import numpy as np
import rasterio


def main():
    card=json.loads((ROOT/'evidence/run_card.json').read_text())
    path=ROOT/'artifacts/quarantine'/f"{card['submission_name']}.tif"
    if sha256(path)!=card['raster_sha256']:
        raise ValueError('Preview source identity mismatch')
    with rasterio.open(path) as src:
        a=src.read(1,out_shape=(650,574),resampling=rasterio.enums.Resampling.average)
    valid=np.isfinite(a)
    hi=float(np.quantile(a[valid],.99))
    if hi<=0:raise ValueError('No nonzero surface to visualize')
    v=np.clip(np.nan_to_num(a)/hi,0,1)
    start=np.array([218,231,214]);mid=np.array([92,143,126]);end=np.array([22,62,67])
    rgb=np.where((v<.5)[...,None],start+(mid-start)*(2*v)[...,None],
                 mid+(end-mid)*(2*(v-.5))[...,None]).clip(0,255).astype('uint8')
    rgb[~valid]=[238,241,233]
    canvas=Image.new('RGB',(650,700),(238,241,233));canvas.paste(Image.fromarray(rgb),(40,5))
    ImageDraw.Draw(canvas).text((38,668),'N ↑  |  100 m study grid  |  OOF research surface',fill=(39,72,69))
    canvas.save(ROOT/'docs/assets/research-surface.png',optimize=True)
    write_json(ROOT/'evidence/visualization.json',dict(source_sha256=sha256(path),
        display='99th percentile stretch after average resampling for illustration only',
        display_upper=hi,model_values_unchanged=True))

if __name__=='__main__':main()
