# Browser QA

Checks all five pages at desktop and mobile sizes, JS errors, source filtering,
feed display, and absence of TIFF/ZIP links. Writes a JSON receipt, with a nonzero
exit status for failure. Browser URLs here are test-only, not application endpoints.

```bash
npm install --prefix .cache/browser --no-audit --no-fund playwright@1.64.0 @sparticuz/chromium@153.0.0
# Start the docs preview with the process tools, or another managed server, on port 8000.
node tests/browser/check.cjs
```

In minimal Linux sandboxes, Chromium may lack NSPR/NSS libraries. The npm package
contains these in `bin/al2023.tar.br`. The tested sandbox unpacked that bundled
archive into `.cache/browser/libs` and ran with
`LD_LIBRARY_PATH="$PWD/.cache/browser/libs/lib"`. No OS packages or browser assets
were fetched from an unapproved host. Ordinary Linux desktop/CI images with these
libraries already installed do not need this step. Screenshots are ignored scratch
files, not new scientific evidence or a submission.

## Sandbox HTTPS caveat

The bundled Chromium does not trust this sandbox’s egress proxy CA. A normal
HTTPS attempt exercised the dated local fallback, not a fresh feed. The public
GitHub Contents endpoint was separately tested anonymously with system TLS
verification and its `Access-Control-Allow-Origin: *` response recorded in
`evidence/browser_transport.json`. For sandbox UI-only QA,
`QA_SANDBOX_PROXY=1` sets Playwright `ignoreHTTPSErrors`; the receipt explicitly
records this limitation. Production site JavaScript never disables certificate
validation or sends credentials. `node tests/browser/feed-unit.cjs` covers nine
remote/fallback/cache/scope cases without networking.
