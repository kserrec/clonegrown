# Simplification and stabilization

This is the September 7–8, 2026 stabilization pass. Current product
behavior is documented in [README.md](README.md) and
[ARCHITECTURE.md](ARCHITECTURE.md). Implementation and local qualification are
complete. The live hosted qualification record is
[pull request #1's checks](https://github.com/kserrec/clonegrown/pull/1/checks).
Release qualification requires all nine CI jobs to pass on the latest revision.

## Completed phases

1. Truthful tests: reproduced clean-main failures; corrected the private-ref
   state-machine model and symbolic-ref test without weakening preservation.
2. Compatibility: explicitly rejected reftable before mutation and verified
   the existing Git 2.29 transaction repair. Full suites passed on Git
   2.29/2.43/2.55, with supported Python endpoints and package smoke checks.
3. Test readability: expanded compressed campaigns, shared the identical
   subprocess helper, and removed incidental error wording. Deterministic
   replay and invariants remained green.
4. Runtime simplification: removed ineffective diagnostic checkpoints and
   redundant forwarding/constants, shared derived task refs, and removed an
   unused helper. On-disk compatibility and safety checks remain intact.
5. Installation: ordinary Python tooling owns the executable. The optional
   skill helper replaces the custom transaction/backup/migration protocol.
   Ten focused installer checks and real isolated install/update/uninstall pass.
6. Documentation: rewrote maintained guides; removed investigation histories
   and HANDOFF; retained only the dated real-repository evidence in docs/archive.

## Phase 7 — Final qualification

- Step 7.1: local compile, shell syntax, install/update/uninstall, and six full
  unit/destructive runs passed across Git 2.29/2.43/2.55 and Python 3.11–3.14
  on Linux. Each run defines 304 tests: Git 2.55 passes all; older Git passes
  301 and skips three reftable capability fixtures. Both hardening modes pass
  on all three Git versions: 57 each on Git 2.55; 56 passes and one reftable
  skip each on older Git. Hosted CI verifies Linux/macOS unit/destructive and
  hardening suites, package smoke checks, and exact Git 2.29 from clean checkouts.
- Step 7.2: passed clone/worktree state-machine seeds 9–13, 50 steps each
  (500 total), and interruption seeds 10–11 for spawn/collect/discard in both
  modes (12 runs). All eight campaign jobs also passed from a clean checkout of
  `ed0afb0`, with that revision recorded in every result. No selected seed failed
  or remained pending. Subsequent corrections normalize test fixture paths
  and clarify documentation; runtime code, seeded transitions, and preservation
  assertions are unchanged. The model tests use a symlinked root on Linux too.
- Step 7.3: the one fresh cold review found four reproduced defects: unchecked
  moved-base-pin cleanup, symbolic-ref substitution between preflight and
  mutation, direct FIFO namespace enumeration on Git 2.29, and unvalidated
  spawn-record reloads. Each now has a focused repair and class regression;
  those pass. The same reviewer independently verified closure on Git 2.55
  and replayed the Git 2.29 FIFO probe successfully. A stale parent-death test
  now checks exact ref preservation before recovery and paired deletion after;
  the reviewer independently verified that focused correction. No finding
  remains open. All 20 final local matrix/campaign jobs passed on frozen source.

Starting main: `6a77f7db378b55d42661ff62e06c94efb374aa59`. Pre-existing
uncommitted runtime safety repairs were preserved and qualified before
simplification. No protocol/schema migration, new dependency, or new feature
is part of this pass. Existing untracked `uv.lock` is outside the change.

Local working notes and logs live under `/tmp/clonegrown-*`; final local logs
and results are in `/tmp/clonegrown-final4`. These are temporary execution
evidence, not additional maintained project documents. The published
`simplification-stabilization` branch and linked PR checks identify the current
candidate. Skipped fixtures and stopped or superseded runs are not passes.
The complete local matrix used a source hash manifest; committed-checkout
campaign results are in `/tmp/clonegrown-committed-campaigns`.
