# PatternBoost Multi-Level Experiments

This repository contains the cleaned experiment harness for the PatternBoost
geometric extremal-search project. The main paper track focuses on three
problems:

- `misr`: maximum independent set of rectangles LP-gap search
- `unit_square`: unit-square stabbing LP-gap search
- `guillotine`: rectangle packing / guillotine nonseparability search

Two exploratory appendix tasks are also implemented and audited separately:

- `epsilon_net`: finite halfplane epsilon-net lower-bound rediscovery
- `graph_separation`: rectangle graphs versus bounded mixed square/segment representations

The repository also contains `formulaboost`, a separate finite-to-family
discovery prototype. It is documented in [docs/FORMULABOOST.md](docs/FORMULABOOST.md)
and does not contribute evidence to the three-problem PatternBoost matrix.

The code generates random search instances, scores every reported candidate
with an exact problem-specific verifier, writes certificate JSON files, and
keeps checkpointable PatternBoost runs for local or NYUAD Jubail HPC execution.

## Repository Layout

```text
src/multilevel/          Python package and CLI
src/multilevel/scorers/  exact scorers and certificate verifiers
src/formulaboost/        finite-to-family FormulaBoost prototype
configs/                 FormulaBoost and experiment configuration files
examples/               tiny explicit examples for smoke tests only
scripts/                local, HPC, collection, and monitoring helpers
tests/                  pytest regression tests
docs/                   handoff docs, current results, archived notes
runs/                   ignored local/HPC output directory
```

Generated artifacts are intentionally ignored by git.

## Setup

Use Python 3.10 or newer. Python 3.11 is recommended.

```bash
cd <repository directory>
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e . -r requirements.txt
```

If `python3 --version` is below 3.10, install a newer Python through conda,
Homebrew, or the NYUAD HPC module system before creating the virtual
environment.

Install PyTorch only if you want transformer-guided PatternBoost sampling:

```bash
python3 -m pip install -r requirements-torch.txt
```

Run the fast checks:

```bash
pytest -q
python3 reproduce.py --mode smoke
```

## Reproducing the Paper

`reproduce.py` is the single entry point. See
[ARTIFACT_EVALUATION.md](ARTIFACT_EVALUATION.md) for the full guide.

```bash
python3 reproduce.py --mode verify                      # re-verify all 81 certificates (minutes)
python3 reproduce.py --mode smoke                       # score and verify small examples (minutes)
python3 reproduce.py --mode single --problem misr --iterations 200   # best cell of one problem
python3 reproduce.py --mode figures                     # regenerate figures and tables
python3 reproduce.py --mode full --iterations 1000000   # all 81 cells (cluster scale)
```

`--problem` is `misr`, `unit_square` or `guillotine`. Each run uses the best
configuration of that problem with the settings reported in the paper, and starts
from a fresh random seed, so scores vary between runs; a short run will usually
not reach the paper's best value. Use `--mode verify` to check the reported
constructions exactly.

The seeds and settings of the original runs are recorded in
`docs/assets/replacement_81_final_20260712/data/final_81_seeds.json`. Add
`--paper-seeds` to `--mode single` or `--mode full` to use the recorded seeds, or
`--seed N` (single mode) for any other seed:

```bash
python3 reproduce.py --mode single --problem unit_square --paper-seeds --iterations 250
```

A recorded seed with the recorded settings is meant for replay, but results can
differ across software versions and hardware. The unit-square record is reached
within a few hundred generations; the MISR and guillotine records took several
hours on the original hardware.

## Running Cells Directly

Generate the paper's final 81-cell matrix. Each row carries its own settings
(size, population, elite size, training interval):

```bash
PYTHONPATH=src python3 -m multilevel.cli final-81-matrix --out runs/final_81_matrix.jsonl
```

Run one PatternBoost cell locally:

```bash
PYTHONPATH=src python3 -m multilevel.cli patternboost-cell \
  --matrix runs/final_81_matrix.jsonl \
  --index 0 \
  --out-root runs/local_test \
  --iterations 20 \
  --model-kind ngram
```

Settings stored in a matrix row take precedence over command-line flags.

Collect and audit results:

```bash
PYTHONPATH=src python3 -m multilevel.cli summary --root runs/local_test --out runs/local_test/summary.csv
PYTHONPATH=src python3 -m multilevel.cli audit --root runs/local_test --out runs/local_test/audit/audit.json --csv runs/local_test/audit/audit.csv
```

## Slurm Cluster

The paper's runs used one 24-hour cell per Slurm array task (4 cores, 16 GB each).
On the cluster, from the repository directory:

```bash
PYTHONPATH=src python3 -m multilevel.cli final-81-matrix \
  --budget-seconds 86400 --out runs/final_81_matrix.jsonl
PYTHONPATH=src python3 -m multilevel.cli make-slurm \
  --matrix runs/final_81_matrix.jsonl \
  --out scripts/final_81_array.slurm \
  --project-dir "$PWD" \
  --results-dir runs/final_81_hpc \
  --time 25:00:00 \
  --partition <partition> \
  --cpus-per-task 4 \
  --mem 16G \
  --runner patternboost
sbatch scripts/final_81_array.slurm
```

Each cell runs until its 24-hour budget or 10^6 generations. Collect and audit the
results with the `summary` and `audit` commands shown above, and monitor a run with
`scripts/monitor_hpc_run.sh JOB_ID runs/final_81_hpc`.

See [docs/HPC_JUBAIL.md](docs/HPC_JUBAIL.md) for the full step-by-step HPC
workflow, including smoke tests, generated Slurm arrays, exploratory runs,
resume commands, collection, and audit.

## Final 81-Cell Evidence

The updated final 81-cell matrix combines the strongest retained configurations
from the July 9 study with the 45 replacement-component runs completed on July
11. It has one independently generated run for every cell in the final
$3 \times 3 \times 3$ component matrix per problem and no repeated-seed axis.

The best exact audited values in this matrix are:

```text
misr         1.5
unit_square 1.538461538461539  (20/13)
guillotine  0.3333333333333333
```

All 81 final certificates pass exact verification: 45 replacement
certificates were freshly recomputed, and 36 retained certificates match their
prior passed audits by configuration, hash, and score.

The updated evidence bundle, including the final 81-row table, epoch histories,
construction renderings, figures, generated tables, and audit metadata, is
stored in
[docs/assets/replacement_81_final_20260712](docs/assets/replacement_81_final_20260712).
The two principal data exports are
[final_81_runs.csv](docs/assets/replacement_81_final_20260712/data/final_81_runs.csv)
and
[final_81_epoch_history.csv](docs/assets/replacement_81_final_20260712/data/final_81_epoch_history.csv).

The full 81-cell report is available as
[PDF](docs/manuscript/patternboost_81_run_analysis.pdf) and
[TeX source](docs/manuscript/patternboost_81_run_analysis.tex). It includes
27 configuration trajectories for each problem, component analyses, exact
construction figures, and a detailed limitations study. See
[docs/FINAL_81_ANALYSIS.md](docs/FINAL_81_ANALYSIS.md) for an artifact map and
rebuild commands.

For a concise manuscript-methods checklist covering the final cohort-specific
hyperparameters, transformer architecture, exact solvers, initialization
ranges, Jubail hardware caveat, and focused convergence plots, see
[docs/COLLABORATOR_EXPERIMENT_DETAILS.md](docs/COLLABORATOR_EXPERIMENT_DETAILS.md).
The compact-versus-scaled transformer check is specified in
[docs/MODEL_CAPACITY_EXPERIMENT.md](docs/MODEL_CAPACITY_EXPERIMENT.md).

The separately audited exploratory run produced:

```text
epsilon_net       1.4545454545454546
graph_separation 0.0 exact, 1.3845054945054946 pressure/search
```

See [docs/EXPLORATORY_RESULTS.md](docs/EXPLORATORY_RESULTS.md). These values
are not part of the three-problem main table.

## Core Commands

Show available components:

```bash
PYTHONPATH=src python3 -m multilevel.cli registry
```

Score, verify, and render one bundled smoke example:

```bash
PYTHONPATH=src python3 -m multilevel.cli score misr examples/misr_small.json --out runs/misr_small.cert.json
PYTHONPATH=src python3 -m multilevel.cli verify runs/misr_small.cert.json
PYTHONPATH=src python3 -m multilevel.cli render runs/misr_small.cert.json --out runs/misr_small.svg
```

Resume a checkpointed cell:

```bash
PYTHONPATH=src python3 -m multilevel.cli patternboost-cell \
  --matrix runs/final_81_matrix.jsonl \
  --index 0 \
  --out-root runs/local_test \
  --iterations 200 \
  --resume
```

For a conceptual map of the 81 rows, see
[docs/EXPERIMENT_MATRIX.md](docs/EXPERIMENT_MATRIX.md). For day-to-day
handoff instructions, see [docs/HANDOFF.md](docs/HANDOFF.md).

License: [MIT](LICENSE)