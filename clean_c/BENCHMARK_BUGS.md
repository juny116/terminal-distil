# Benchmark bugs found via teacher-audit of near-misses (terminal-bench)

Our funnel + Claude-as-teacher audit of genuine near-miss failures surfaces a high rate of
**benchmark bugs** — cases where the student is correct and the test/fixture is wrong. The
static funnel (`mine_failures.py`) misses most of these; they need an answer-knowing audit.

## Harvest 2 (gate2b, 50 tasks): 8 near-misses audited → 6 benchmark bugs

| task | type | evidence (student was right) |
|---|---|---|
| **articulation_points_bridges** | hardcoded expected | test hardcodes a 5-edge toy-graph answer (`crit=["D"]`); real graph has 60+ edges. Student's Tarjan = 27 nodes/41 bridges, **independently reproduced by networkx**. Unpassable. |
| **apt_cache_depends_circular** | truncated-preview expected | test hardcodes 4 packages from the file's first-5-line *preview comment*; real data has ~14 genuine cycles (docker↔runc↔containerd, gcc↔binutils, …). Correct answer = 14. Unpassable. |
| **ansible_async_task_status_check** | spec⊥test | instruction defines failure as `rc!=0 OR finished!=1` (→6 jobs); test hardcodes only the 4 `finished=0` jobs and asserts `len==4`. Mutually contradictory. |
| **a_star_pathfinding** | spec⊥test | instruction: `path_length = number of steps` (N-1); test asserts `path_length == len(coords)` (N). Off-by-one forced by the test. (borderline: fixable by obeying test over spec.) |
| **ar_archive_index_corrupted** | corrupted fixtures | shipped `obj/*.o`, `test_calc.c` are bash-script text; `.o`/`.a` are UTF-8-mangled (U+FFFD runs, no ELF magic). Intended repair impossible; reconstruction forced. (borderline: student could pass by naming 4 objects.) |
| **attribute_section_custom_placement** | success mislabeled | the recorded trajectory **passes every assertion**; harvested/labeled as failure. (Also: instruction falsely claims the code compiles — header/impl signature mismatch.) |

Genuinely recoverable (2/8): **ansible_inventory_dynamic_script** (flat vs nested group structure → grader counts top-level keys), **ansible_template_rendering_error** (missed a 4th `{app_name}` single-brace defect; over-trusted `--syntax-check`).

## Harvest 1 (gate2, 30 tasks): 8 near-misses → 2 benchmark bugs
- **acl2_induction_scheme_selection**: test reads `output/.../files/functions.lisp`, a path the harness never provisions → FileNotFoundError. Student's 11 classifications all pass.
- **alloy_scope_bitwidth_configuration**: test hardcodes `expected_max=4095`; deployed data maxes at 16383. Unpassable honestly.

## Tally
- Audited near-misses: ~16 (8 + 8)
- **Benchmark bugs: ~8 (≈ 50%)** (hardcoded/toy-graph expected, truncated-preview expected, spec⊥test contradictions, corrupted fixtures, success-mislabeled, unprovisioned harness paths)
- Genuinely recoverable: ~7 (amass, alembic, agda, alloy_analyzer, airflow, ansible_inventory, ansible_template) + ~2 borderline (a_star, ar_archive)

## Implications
1. **Standalone finding**: ~half of terminal-bench *near-miss* failures are benchmark bugs.
   Static signals miss them; an answer-knowing teacher audit catches them. Strong support for
   the benchmark-contamination thesis and for why verifier-as-ground-truth (which arm-C's
   reward-0→1 gate depends on) is fragile.
2. **For the capability experiment**: the recoverable-prefix yield per harvested task is LOW
   (~half of near-misses are unrecoverable benchmark bugs). Scaling C1 to hundreds of
   examples via fresh harvest is expensive (high benchmark-bug attrition). Either accept a
   small pilot (~7-9 prefixes) or use the teacher API to scale hint generation while filtering
   bugs.
