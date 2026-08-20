# Reproduction notes

The complete campaigns are intentionally split into isolated commands because aggregate runners can exceed interactive execution limits.

## One deterministic test

```bash
python3 run_one.py exact_base_dirty
```

Names are listed in `hardening_suite.py` under `TESTS`.

## One crash failpoint

```bash
python3 run_crash_case.py collect collect.after_fetch
python3 run_crash_case.py discard discard.after_delete
```

## State-machine fuzzing

```bash
python3 state_machine_fuzz.py --start 0 --seeds 1 --steps 50 --output fuzz-example.json
```

## Random process kill

```bash
python3 random_kill.py spawn --start 0 --count 1 --output kill-spawn.json
python3 random_kill.py collect --start 0 --count 1 --output kill-collect.json
python3 random_kill.py discard --start 0 --count 1 --output kill-discard.json
```

## Scaling

```bash
python3 scaling_v2.py tiny 4 --output scale-tiny.json
python3 manyrefs_v2.py 1000 --output manyrefs-1000.json
python3 concurrency_v2.py 16 --output concurrency.json
python3 gc_compare.py
```

## Focused probes

```bash
python3 partial_clone_probe.py
python3 narrow_clone_probe.py
python3 ref_compaction_probe.py
python3 self_host_probe.py
python3 io_fault_probe.py
```

## Rebuild consolidated results

```bash
python3 consolidate_results.py
```
