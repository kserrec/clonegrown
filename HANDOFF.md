# Session handoff

Written 2026-08-28 (updated after Phase 1 closed). This handoff becomes stale
when Phase 4 Step 4.1 is completed, `PLAN.md` changes the next unfinished
Step, or this checkout moves away from `main`.

## Exact stop point

- Work is on `main`, tracking `origin/main`, with the complete Phase 1 change
  set **uncommitted** in the working tree (Kyle has chosen not to read code
  until all phases are done; commit at wrap-up).
- Phase 1 (Steps 1.1 through 1.13) is complete and closed by the Step 1.13
  fresh review, which found no open Phase 1 finding.
- Phase 2 Step 2.1 is complete: `WorkerRecord.validate` is the one
  table-driven validator, with the lease and quarantine fields reserved and
  validated but not yet set by any command.
- Phase 2 Step 2.2 is complete: workers are leased from spawn, `release`
  and `claim` exist in the API and CLI, discard and recovery deletion require
  a released lease, and a collected worker is one-shot.
- Phase 2 Step 2.3 is complete: discard of a collected worker enumerates
  ignored paths by name and requires `--discard-ignored`.
- Phase 2 Step 2.4 is complete: worktree task branches carry a private
  ownership ref created with them in one transaction and are deleted only by
  a verifying transaction; admin-directory removal is error-checked and
  absence-verified; conflicts retain evidence and are reported.
- Phase 2 Step 2.5 is complete: discard fingerprints, quarantines,
  rechecks, deletes with errors enabled, proves absence, and records a
  terminal status only when everything is clean; recovery resumes
  quarantines and never labels residue gone.
- Phase 2 Step 2.6 is complete: a diverged published spawn is preserved as
  `broken` with a content-free description; the worktree add/persist window
  is closed by gitdir-based ownership.
- Phase 2 (Steps 2.1 through 2.7) is complete and closed by the Step 2.7
  cold review; its six confirmed defects were fixed and re-reviewed in the
  same pass (details under Step 2.7 in `PLAN.md`). A Phase 2 bughunt then
  found and fixed eight more (checked-out branch deletion, three stuck
  cleanup states, Unicode-digit and non-UTF-8 path crashes, validator bypass,
  fingerprint blind spots); its record follows Step 2.7 in `PLAN.md`.
- Phase 3 (Steps 3.1 through 3.5) is complete and closed by the Step 3.5
  cold review: create-only allocation, validated request indexes, a
  non-mutating `status` audit with stable issue codes, and ownership-scoped
  `recover` reconciliation; its five review findings were fixed in the same
  pass (records under Phase 3 in `PLAN.md`). A Phase 3 bughunt then found
  and fixed eight more, chiefly namespace writes that followed symbolic refs
  onto canonical's own branches; its record follows Step 3.5 in `PLAN.md`.
- The next `$next` pass is the first unfinished Step of **Phase 4 — Restore
  exact Git semantics and safe operational errors**; follow its exact scope
  in `PLAN.md`.

## Completed through this stop point

- Steps 1.1 through 1.11 as recorded in `PLAN.md`.
- Step 1.12 bound backup relocation to token-bearing reservations and to
  identity plus ownership evidence for every deletion and restoration path.
  A bughunt against that working tree found and fixed seven installer defects
  (non-UTF-8 paths under a UTF-8 locale, identity-only trust defeated by inode
  reuse, a false rollback message, a locale-dependent test, three disagreeing
  ownership predicates, a FIFO blocking the installer, and updates failing
  under a non-UTF-8 source path), each with a regression and three cold-review
  rounds; details are under Step 1.12 in `PLAN.md`.
- Step 1.13's fresh review closed Phase 1; its two low notes were fixed in the
  same pass (`SIGPIPE` trapped with a regression; README and architecture now
  say a caught signal after commit can leave authenticated backups).

## Verified close state

- `python3 -m unittest discover -s tests`: 147 tests passed.
- Campaign cases (init/spawn/collect/discard crash matrices, dirty-ready
  recovery, recovery resilience, hook provisioning, private hook boundary) in
  clone and worktree modes: passed.
- Five direct CLI output probes, retired-claim search, out-of-checkout byte
  compilation, `sh -n install.sh`, and `git diff --check`: passed.
- No session-owned Python, Git, shell, or reviewer process remains running.
- No pending user ruling or manual action blocks Phase 4.
