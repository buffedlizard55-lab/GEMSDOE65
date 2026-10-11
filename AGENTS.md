# Working agreement

1. Read `README.md` in full, including the archived original user request, at the start of every work session. Then read `research/preregistration.md`, `research/review.md`, and `evidence/run_card.json`.
2. This lane is selection-bias-aware SAR-PU only. Never build a candidate from a prior submission; prior rasters are forensic/audit inputs only.
3. Reuse the immutable template snapshot; verify every file hash in `evidence/shared_template_pin.json`. Do not create a private evaluator, metric, writer, or gate fork.
4. Fail closed. No public TIFF or ZIP, including unlinked files, if any scientific, convergence, canary, uniqueness, provenance, or format requirement is missing/failed. A negative result is a deliverable. Local format pass is not organizer acceptance.
5. Label performance as HOLDOUT-DTI with evaluator, count, and CI, or ORGANIZER-CONFIRMED with a genuine receipt. User/sibling claims are unverified. Do not convert forecasts into scores.
6. Respect the three-experiment / two-hour cap. The initial three-scenario experiment is consumed. Tests with synthetic fixtures are not new geological experiments. A new experiment requires a fresh preregistration and must not silently reuse a tuned holdout.
7. No automatic DrivenData upload or weekly-slot selection. Never request/store passwords, tokens, or session cookies. The selector must independently verify the live cap and acceptance rules.
8. Keep raw data, cached arrays, prior rasters, and quarantine files out of Git. Keep deterministic manifests, code, and honest receipts in Git. Do not expose negative model artifacts through the public site.
9. Run all tests, `scripts/build_site.py`, and the site integrity checker. Review in three passes. Keep next-session blockers explicit.
10. Maximize P(Win) by preserving slots and measuring real improvement. Own the Outcome by verifying actual files and recording failures, not by overstating success.
