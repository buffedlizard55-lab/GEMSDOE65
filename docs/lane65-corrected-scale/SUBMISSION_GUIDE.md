# Executive summary — how a GEMS GeoTIFF would be submitted

**Today the answer is: do not submit.** The gate did not pass; the artifact is research only.

1. Open the [submissions page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/)
   and choose **New submission**.
2. Verify the site says CLEARED and that the sha256 matches your download.
3. Upload `gems65-sarprop-em-v2-20261011-9b1c65d-zeros.tif` (or a zip containing exactly that TIFF);
   it is single-band float32, EPSG:32611, 3730 × 3292, 100 m, all-finite, values in [0, 1], zeros
   outside the footprint, no NaN inside, no positive mass on the mapped catalogue.
4. Paste the note (≤ 140 chars): `GEMS65 SAR-EM propensity PU v2, corrected-scale continuous e(x); both instruments tie (bias-matched +3.4e-5 n.s.); research only`
5. Record the portal receipt in `registry/run-card.json` as ORGANIZER-CONFIRMED evidence tied to
   that sha256. Nothing here uploads anything for you.

The earlier portal rejection "Predicted values must be in range [0, 1]" is why the primary artifact
is the strict all-finite encoding; the NaN-outside variant is diagnostics only (IR-65-102).
