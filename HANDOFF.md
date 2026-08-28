# Session handoff

Written 2026-08-27. This handoff becomes stale when Phase 1 Step 1.8 is
completed, `PLAN.md` changes the next unfinished Step, or this checkout moves
away from `main`.

## Exact stop point

- Work is on `main`, tracking `origin/main`.
- Phase 1 is the whole contract-and-installer remediation body. Its individual
  parts are Steps 1.1 through 1.11; use those terms literally.
- Steps 1.1 through 1.7 are complete. The next `$next` pass is **Phase 1,
  Step 1.8 — State recovery guarantees at represented checkpoints**.
- Step 1.8 is prose-only. Follow its exact scope in `PLAN.md`: correct the
  `recovery.py` module contract and nearby recovery descriptions that promise
  more than the represented durable checkpoints provide. Do not change
  executable behavior unless Kyle separately authorizes a different Step.
- Steps 1.9 through 1.11 remain pending after Step 1.8. Step 1.11 is the final
  cold review for the complete Phase 1 diff.

## Completed in this session

- Step 1.1 replaced unconditional safety, isolation, idempotency, integration,
  recovery, and evidence claims with the verified current alpha boundary and
  froze the later custody contract.
- Steps 1.2 and 1.4 through 1.6 replaced the custom installer's unchecked
  replacement behavior with four-target installation identity, staged
  publication and rollback, filesystem-identity-bound stage cleanup, a
  colon-safe command launcher, and exact preflight framing/path validation.
- Step 1.3 cold-reviewed those changes and recorded seven bounded remediation
  findings. The first three were resolved by Steps 1.4 through 1.6.
- Step 1.7 documented the real hook boundary: only the default private
  `.git/hooks` location is separate. A copied `core.hooksPath` can resolve
  outside the worker; absolute values receive a warning, while tilde-prefixed
  and traversal-heavy values can escape without it. A final fresh review found
  no remaining Step 1.7 issue.
- `PLAN.md` now defines Phase versus Step near the top so future status reports
  do not call Phase 1 a Step.

## Verified close state

- `python3 -m unittest discover -s tests`: 31 tests passed.
- `python3 -m unittest discover -s tests -p 'test_installer.py'`: 13 tests
  passed.
- `python3 tests/campaign/hardening_suite.py --one provisioning_hooks`: passed
  and returned the expected absolute-hook shared-dependency warning.
- `sh -n install.sh`, `python3 -m compileall -q clonegrown tests`, and
  `git diff --check`: passed.
- No session-owned Python, Git, shell, or reviewer process remains running.
- No pending user ruling or manual action blocks Step 1.8.
