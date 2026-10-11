# `vendor/template60` — second pinned copy of the shared `gems57` template

**Why this directory exists.** This repository already vendors the canonical shared
template at `vendor/template58/` (pinned to `buffedlizard55-lab/58GEMSDOE` tree
`3ccda56feaca7215e2ceef01d755e0c7b5fd486e`, per-file blob SHA-1s and SHA-256s in
`docs/data/shared_template_pin.json`). The lane-65b session
(`arena/98cb5eb2-gemsdoe65`, 2026-10-11) was built against the copy of the same
template published by the sibling repository `60GEMSDOE`, and that copy has diverged.
Rather than keep a private fork inside `src/` (which the standing brief forbids, and
which shadowed `gems57` for the canonical test suite), the second pin is vendored
here, labelled, and reported as an irregularity for the owner to consolidate.

**Nothing in this directory was modified.** Files are byte-identical to
`60GEMSDOE/src/gems57/` at the commit this session branched from.

## Divergence measured on 2026-10-11 (SHA-256, first 12 hex)

| module | template58 (canonical) | template60 (this pin) | status |
|---|---|---|---|
| `__init__.py` | `bd7f12b45caf` | `bd7f12b45caf` | identical |
| `emit.py` | `05c473e736e4` | `05c473e736e4` | identical |
| `evaluate_holdout.py` | `ad86640b46f3` | `ad86640b46f3` | **identical** — the DTI evaluator |
| `metric.py` | `4afe10cbaa22` | `4afe10cbaa22` | **identical** — the official metric |
| `network.py` | `d5e53d7df182` | `d5e53d7df182` | identical |
| `spatial.py` | `fad7b09db9ef` | `fad7b09db9ef` | identical |
| `gates.py` | `5a671f6f99b7` | `7c57f70dbba5` | differs |
| `grid.py` | `ce549e30814b` | `b96df7ec0f33` | differs (writer default mode) |
| `holdout.py` | `5434549bee01` | `7a0a84176986` | differs (see below) |
| `submission_writer.py` | `627879b3bbe1` | `41220185ac28` | differs (NaN vs zeros) |
| `uniqueness.py` | `99a0683fed3f` | `1c5094b81427` | differs |
| `validate.py` | `b4dca03101d9` | `e7849554b47f` | differs |

Consequences that matter for the numbers in `evidence/`:

1. **The DTI numbers are reproducible under the canonical pin.** `evaluate_holdout.py`
   and `metric.py` — the two modules that compute every HOLDOUT-DTI on this lane's
   pages — are byte-identical between the pins. `quadrant_ids` in `holdout.py` is also
   byte-identical.
2. **The fold constructor is not in the canonical pin.** `holdout.buffered_component_draw`
   (whole-component, label-blind, buffered LOQO draw; `split_version`
   `buffered-whole-components-loqo-v2`) exists only in this pin. template58 exposes
   `build_buffered_holdout_context` / `HoldoutContext` instead and marks its
   `build_holdout` as legacy. Porting this lane's instruments to that API is real work
   and would change the folds, so it is left to the owner as the consolidation step.
3. **The two pins contradict each other on the portal format**, in their own docstrings:
   * template58 `grid.write_submission`: `mode="nan"` "is the submission representation";
     `mode="zeros"` "is retained for internal diagnostics and is **not portal-format
     compliant**".
   * template60 `grid.write_submission`: `mode="zeros"` "is the only submission-compatible
     mode"; `mode="nan"` "is retained for local diagnostics only … a prior portal range
     error does not establish NaN as its cause".

   This artefact was written with template60's `submission_writer` in all-finite `zeros`
   mode, because the organizer's own reference solution
   (<https://github.com/drivendataorg/gems-prize-reference-solution>) writes an all-finite
   raster with **no** `nodata` tag, and because NaN primaries are what accompanied the
   portal rejection *"Predicted values must be in range [0, 1]"* this lane was asked to
   fix. The contradiction is recorded as `IR-65B-FORMAT-01` and is an owner decision:
   it cannot be settled from this sandbox, which cannot reach `drivendata.org`.

## Import discipline

`scripts/_bootstrap.py` puts `vendor/template60` at the front of `sys.path` for this
lane's scripts and then **asserts** which copy was actually loaded, so a silent
version swap cannot change a published number. Test modules in `tests/` must not import
`gems57` except through the canonical pin (`from gems65 import common` first), because
`gems57` is a single module name per process: whichever copy is imported first is the
one every later import sees.
