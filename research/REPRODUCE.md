# Reproduction notes

This repository contains two different kinds of evidence:

1. **Preserved historical evidence** from the original falsification and
   hardening campaign.
2. **Current harnesses** that exercise the current `clonegrown` package.

Those are not interchangeable. The current harnesses can test the current
checkout, but they cannot recreate the historical `RESULTS.json` byte for byte
because the frozen candidate and several campaign inputs are absent.

## Preserved historical evidence

- `REPORT.md` is the narrative adversarial evidence report.
- `RESULTS.json` is the recovered consolidated machine-readable result set for
  the frozen `cws.py` candidate identified in `REPORT.md`.
- `FALSIFICATION.md` is the earlier independent-clone-versus-worktree
  falsification report.

The preserved recovered files have these SHA-256 digests:

```text
be38e48911d5a7fc2096b23bee251a05b286ebd9288c43c87bb10687db6cd17c  RESULTS.json
51e1b2d6ca4aa12280febefae5c53865a6b1389adc86394dfba84a200446baff  FALSIFICATION.md
```

## Requirements for current checks

Run commands from the repository root on a POSIX system with Git and Python
3.11 or newer. The current implementation uses `fcntl`, so it does not run
natively on Windows.

The harnesses invoke the current package through `tests/legacy_cli.py` (the
positional research interface, `clonegrown.legacy_cli`); they do **not**
invoke the absent frozen `cws.py` candidate.

## Current deterministic checks

Run one named adversarial case:

```bash
python3 tests/hardening_suite.py --one exact_base_dirty
```

Names are defined by `TESTS` in `tests/hardening_suite.py`. Run the whole
current suite while keeping its consolidated output outside the checkout:

```bash
CWS_RESULTS_PATH=/tmp/clonegrown-hardening-results.json python3 tests/hardening_suite.py
```

Run the current unit tests:

```bash
python3 -m unittest discover -s tests -v
```

## Current crash and generated campaigns

The random-kill campaigns create temporary repositories, kill only the child
processes they launch, and write their requested result files under `/tmp`:

```bash
python3 tests/random_kill.py spawn --start 0 --count 1 --output /tmp/clonegrown-kill-spawn.json
python3 tests/random_kill.py collect --start 0 --count 1 --output /tmp/clonegrown-kill-collect.json
python3 tests/random_kill.py discard --start 0 --count 1 --output /tmp/clonegrown-kill-discard.json
```

Individual failpoint cases append one JSON row per run to
`CWS_CRASH_RESULTS_PATH` (default `tests/crash-results.jsonl`, which is
git-ignored):

```bash
CWS_CRASH_RESULTS_PATH=/tmp/clonegrown-crash.jsonl python3 tests/run_crash_case.py collect collect.after_fetch
CWS_CRASH_RESULTS_PATH=/tmp/clonegrown-crash.jsonl python3 tests/run_crash_case.py discard discard.after_delete
```

That generated file is not part of the preserved historical evidence.

## Current comparative probes

These probes accept an output path, so their results can stay outside the
checkout:

```bash
python3 tests/scaling_v2.py tiny --workers 4 --output /tmp/clonegrown-scale-tiny.json
python3 tests/concurrency_v2.py 16 --output /tmp/clonegrown-concurrency.json
```

The following present-day probes are runnable, but each writes a fixed JSON
file inside `tests/`:

```bash
python3 tests/gc_compare.py
python3 tests/shared_state_compare.py
python3 tests/io_fault_probe.py
```

Their generated files are, respectively, `tests/gc-concurrency.json`,
`tests/shared-state-comparison.json`, and `tests/io-fault-result.json`. They
are current experimental output, not replacements for `research/RESULTS.json`.

## State-machine fuzzer

`tests/state_machine_fuzz.py` originally imported the frozen `cws` module. It
now drives the current package's Python API directly, so it is a current
experiment, not a rerun of the historical campaign:

```bash
CWS_FUZZ_ROOT=/tmp/clonegrown-fuzz python3 tests/state_machine_fuzz.py --start 0 --seeds 1 --steps 50 --output /tmp/clonegrown-fuzz.json
```

## Missing historical inputs

The following artifacts named by the original report or earlier reproduction
guide are not in this repository:

- the frozen `cws.py` candidate;
- `run_one.py` (the current deterministic suite instead supports `--one`);
- `manyrefs_v2.py`;
- `partial_clone_probe.py`;
- `narrow_clone_probe.py`;
- `ref_compaction_probe.py`;
- `self_host_probe.py`;
- `consolidate_results.py`;
- the original `hardening-results.jsonl` and `crash-results.jsonl` inputs.

Because `consolidate_results.py` and its raw inputs are missing, there is no
honest command in this checkout for rebuilding the preserved historical
`RESULTS.json`. That file should be treated as a recovered research artifact;
current reruns should be stored separately and compared explicitly.
