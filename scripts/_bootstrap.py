"""Put this lane's pins on sys.path for scripts run without an editable install.

Two copies of the shared ``gems57`` template are vendored in this repository
(``vendor/template58`` = the canonical pin used by the first lane-65 session, and
``vendor/template60`` = the pin this lane was built against; see
``vendor/template60/PROVENANCE.md`` for the measured divergence).  ``gems57`` is a
single module name per process, so the copy that is imported first wins for
everything afterwards.  This bootstrap puts template60 first for this lane's
scripts and :func:`assert_template60` verifies what actually got loaded, so a
silent version swap can never change a published number.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "vendor" / "template60"
for p in (str(ROOT / "src"), str(TEMPLATE)):
    if p not in sys.path:
        sys.path.insert(0, p)


def assert_template60(*objs) -> None:
    """Fail loudly unless ``gems57`` resolved to this lane's pin.

    Accepts modules or objects imported from them (functions/classes), so the
    guard can sit next to any import style.
    """
    for o in objs:
        mod = o if hasattr(o, "__file__") else sys.modules.get(getattr(o, "__module__", ""), None)
        f = str(getattr(mod, "__file__", "") or "")
        name = getattr(mod, "__name__", None) or getattr(o, "__name__", repr(o))
        if "template60" not in f:
            raise SystemExit(
                f"shared-template mismatch: {name} loaded from {f or '<unknown>'}, "
                f"expected something under {TEMPLATE}. Another pin (vendor/template58) "
                "won the import race; refusing to produce numbers with the wrong tool.")
