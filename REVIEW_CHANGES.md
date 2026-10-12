# Changes made in response to the artifact reviews

Baseline = the repository the reviewers received (anonymous.4open.science mirror). It does not contain
`reproduce.py` or `ARTIFACT_EVALUATION.md`; both are added here as whole files. Every other change below
is a patch to a file already in that repository.

## Review comments and resolution

| # | Reviewer comment | Status |
|---|---|---|
| 1 | Mode 3 (`--mode single`) ran the same MISR cell for every `--problem`: `_find_matrix_index` used keys `repr`/`local`/`surr`, the matrix uses `representation`/`local_search`/`surrogate`, so every lookup missed and fell back to row 0. | Fixed |
| 2 | The unit-square best cell is not in `matrix --stage main` (`symmetry_crossover_hillclimb` belongs to the replacement design), so a key fix alone would not run it. | Fixed |
| 3 | Mode 3 did not use the paper's settings for MISR/guillotine (paper: n=8, population 32, elite 6, train every 7; script: n=12, population 16, elite 4, train every 10). The final 81 cells come from three runtime cohorts. | Fixed |
| 4 | `make-slurm` capped every run at 100 generations; paper used a 24 h budget and a 10^6 generation cap. | Fixed |
| 5 | `scripts/analyze_model_capacity.py` crashed on the Table 4 matrix (missing `reference_score`). | Could not reproduce with the current code; analyzer made robust to a missing field |

## Before vs after

| Area | Before | After |
|---|---|---|
| `--mode single --problem X` | Always ran row 0 of the generated matrix (MISR `endpoint_sequence_pair/sequence_pair_pivot/exact_lp_gap_pressure`, not among the paper's best cells), with a warning on stderr. `--problem` only changed n/grid/population/elite. | Runs the paper's best cell for X, with its cohort's settings; unknown cell exits with an error. Cell written to `runs/single_X/best_cell.jsonl`. |
| MISR best cell settings | n=12, grid 8, pop 16, elite 4, train every 10 | n=8, grid 8, pop 32, elite 6, train every 7 (retained cohort) |
| Guillotine best cell settings | n=9, pop 16, elite 4 | n=8, grid 8, pop 32, elite 6, train every 7 |
| Unit-square best cell | Not reachable (not in main matrix) | `sqstab_exact_grid / symmetry_crossover_hillclimb / exact_stab_gap_pressure`, n=20, grid 16, pop 32, elite 12, pool 128, 4 immigrants, train every 10 |
| `--mode full` matrix | Original `--stage main` design (81 cells, but not the paper's final 81); library defaults for sizes | `build_final_81_matrix()`: the paper's final 81 cells, per-cohort settings, 24 h budget (86,400 s) |
| Slurm generator | `ITERATIONS` default 100; fallback defaults mixed cohorts (pop 32/elite 6 with train 10, n 12) | `ITERATIONS` default 1,000,000; fallback defaults consistently the retained cohort (train 7, n 8) |
| Matrix for HPC | Docs said `matrix --stage main` | New `multilevel.cli final-81-matrix`; docs updated |
| Capacity analyzer | `spec["reference_score"]` required | Falls back to the registry (`MODEL_CAPACITY_TOP_CONFIGS`) |
| Console output | `≈` in printed targets crashed on Windows cp1252 consoles | `~` |

### Cohorts used for the final 81 cells

Rule reproduces `source_cohort` and `population_size` in
`docs/assets/replacement_81_final_20260712/data/final_81_runs.csv` for all 81 rows.

| Cohort | Cells | Settings |
|---|---:|---|
| Retained (representation and local search both from the original design) | 36 | n=8, grid 8, pop 32, elite 6, pool 32, 0 immigrants, train every 7 |
| Replacement | 42 | MISR/guillotine n=12, grid 8; unit-square n=20, grid 16; pop 16, elite 4, train every 10 |
| Unit-square follow-up (`sqstab_exact_grid` + `symmetry_crossover_hillclimb`) | 3 | n=20, grid 16, pop 32, elite 12, pool 128, 4 immigrants, resolution islands, train every 10 |

## Files changed

- `reproduce.py` (added as a whole file): single mode and full mode use the final-81 table; broken lookup removed.
- `src/multilevel/components.py`: `RETAINED_RUNTIME_OVERRIDES`, `build_final_81_matrix()`.
- `src/multilevel/cli.py`: `final-81-matrix` command.
- `src/multilevel/launch.py`: Slurm defaults.
- `scripts/analyze_model_capacity.py`: `_reference_score` fallback.
- `ARTIFACT_EVALUATION.md` (added as a whole file), `README.md`, `docs/EXPERIMENT_MATRIX.md`, `docs/HPC_JUBAIL.md`: docs.

## Verification (reviewers' repository + these changes, clean copy)

| Check | Result |
|---|---|
| `--mode verify` | 81 passed, 0 failed, 0 skipped |
| `--mode smoke` | passed |
| `--mode single`, 5 iterations, misr / unit_square / guillotine | all exit 0, each in its own correct cell directory, e.g. `.../unit_square/sqstab_exact_grid/symmetry_crossover_hillclimb/exact_stab_gap_pressure` |
| `multilevel.cli final-81-matrix` | wrote 81 rows |
| `make-slurm` on that matrix | `ITERATIONS` default 1000000, `TRAIN_EVERY` 7, `N` 8 |
| `scripts/analyze_model_capacity.py` on a freshly generated capacity matrix | runs |
| `--mode figures` | passed |
| `pytest tests` | 73 passed |
| Cohort table vs `final_81_runs.csv` | 81/81 cells match |

Not run: `--mode full` (about 2,000 CPU-hours) and an actual Slurm submission; the generated array
script was only inspected. The `analyze_model_capacity.py` crash reported by the reviewer could not be
reproduced; the change only adds a fallback for a missing `reference_score`.

## Not changed

- `ARTIFACT_EVALUATION.pdf` is a rendered copy of the `.md` and is out of date; re-export or drop it.
- Short runs will not reach the paper's record scores (3/2, 20/13, 1/3). `--mode verify` re-checks the
  committed certificates.
