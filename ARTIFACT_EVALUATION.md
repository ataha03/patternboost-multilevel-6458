# Artifact Evaluation Guide

**Paper:** "Towards Learning-Guided Discovery of Extremal Geometric Constructions: A PatternBoost Study"  
**Venue:** ALENEX 2027  
**Artifact repository:** this directory

---

## Overview

This artifact accompanies a paper that uses the PatternBoost framework to automatically discover
extremal geometric constructions — configurations that expose LP-relaxation integrality gaps and
algorithmic hardness.  The code studies three problems:

| Problem | What is searched | Paper's best result |
|---------|-----------------|---------------------|
| MISR | Integrality gap of the clique-LP for Maximum Independent Set of Rectangles | **3/2 = 1.500** |
| Unit-square stabbing | Integrality gap of the set-cover LP for axis-parallel unit-square stabbing | **20/13 ≈ 1.538** (automated); **14/9 ≈ 1.555** (staircase) |
| Guillotine cutting | Destroyed fraction under optimal recursive guillotine cuts | **1/3 ≈ 0.333** |

Every reported construction is stored as an independently verifiable certificate JSON file.  The
primary claim reviewers can check is that these 81 certificates are genuine: their exact scores are
re-computable from the stored geometric objects alone, without re-running the search.

---

## Solver License

**No commercial solver license is required.**

All exact oracles use only open-source components:

- **HiGHS** LP solver — accessed via `scipy.optimize.linprog` (bundled with SciPy)
- **Custom branch-and-bound** integer solvers for MISR and unit-square stabbing
  (`src/multilevel/scorers/misr.py`, `src/multilevel/scorers/unit_square.py`)
- **Custom dynamic-programming** guillotine scorer (`src/multilevel/scorers/guillotine.py`)

All three are self-contained Python modules with no external solver dependency beyond NumPy and
SciPy, which are installed from `requirements.txt`.

---

## Hardware Requirements

| Evaluation mode | Recommended hardware | Expected time |
|----------------|---------------------|---------------|
| **Certificate verification** | Any laptop or workstation | < 5 minutes |
| **Smoke test** | Any laptop or workstation | < 5 minutes |
| **Single cell (short)** | ≥ 4 cores, ≥ 4 GB RAM | 30 min – 2 h |
| **Single cell (full budget)** | ≥ 4 cores, ≥ 16 GB RAM | 24 h |
| **Full 81-cell matrix** | Cluster with ≥ 81 × 4 cores | ~2 000 CPU-hours |

The full 81-cell matrix was run on AMD EPYC 7742 nodes at 2.25 GHz, 4 cores and 16 GB RAM per
cell, each for 24 hours.  Reviewers are **not** expected to reproduce the full matrix; certificate
verification and the smoke test are sufficient to confirm the main claims.

---

## Setup

### Prerequisites

- **Python 3.10 or newer** (Python 3.11 recommended)
- `pip` (comes with Python)
- Internet access for the initial `pip install`

### Step 1 — Create a virtual environment

```bash
cd /path/to/patternboost-multilevel-6458
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows PowerShell
```

### Step 2 — Install core dependencies

```bash
pip install --upgrade pip setuptools wheel
pip install -e . -r requirements.txt
```

This installs the `multilevel` package (the search harness, exact scorers, and CLI) together with
NumPy 2.0.2 and SciPy 1.13.1.

### Step 3 — (Optional) Install PyTorch for transformer-guided sampling

The search loop can use either a lightweight n-gram model (no PyTorch required) or a small
decoder-only transformer.  The paper used the transformer for its main results.

```bash
pip install -r requirements-torch.txt   # installs PyTorch 2.8.0
```

Without PyTorch, every mode works but uses the n-gram fallback.

### Step 4 — (Optional) Install analysis dependencies for figure generation

```bash
pip install -r requirements-analysis.txt   # matplotlib, pandas, pypdf
```

### Step 5 — Verify installation

```bash
PYTHONPATH=src python3 -m multilevel.cli registry
```

This prints the full 3 × 3 × 3 component grid for each problem.  If it runs without error, the
installation is complete.

---

## Evaluation Modes

All modes are driven by the single script `reproduce.py`:

```
python reproduce.py --mode <mode> [options]
```

---

### Mode 1: Certificate verification  *(< 5 minutes — recommended starting point)*

Re-verify all 81 committed best-certificate JSON files from scratch.  Each file is re-scored by
the exact oracle independently of the search code.  This checks:

- The stored geometric objects (rectangles / squares) produce the reported LP and integer optima.
- The SHA-256 content hash embedded in the file matches the object content.
- The solver status is "optimal" for each LP and ILP sub-problem.

```bash
python reproduce.py --mode verify
```

Expected output: `79 passed, 0 failed, 2 skipped (no certificate)` followed by
`[OK] All present certificates verified.`

Two of the 81 configurations produced no improving certificate (their scores never exceeded the
trivial threshold), so their certificate files are absent; the script reports these as "skipped"
rather than failures.  The `artifact_mapping.csv` in `run_artifacts/` records the mapping from
every configuration to its certificate file.

The certificates reside in:

```
docs/assets/replacement_81_final_20260712/run_artifacts/
  artifact_mapping.csv                       ← config → certificate mapping (81 rows)
  <problem>/<repr>/<local>/<surrogate>/
    certificates/best_iter<N>_<hash>.json    ← exact-score certificate
    renderings/best_iter<N>_<hash>.svg       ← geometric rendering
```

You can also verify a single certificate manually — here is the 20/13 unit-square stabbing result:

```bash
PYTHONPATH=src python3 -m multilevel.cli verify \
  "docs/assets/replacement_81_final_20260712/run_artifacts/unit_square/sqstab_exact_grid/symmetry_crossover_hillclimb/exact_stab_gap_pressure/certificates/best_iter000190_9c9815504d50.json"
```

---

### Mode 2: Smoke test  *(< 5 minutes)*

Scores one tiny example per problem and runs a 20-generation search to confirm the full pipeline
(scorer → surrogate → model → mutation → verifier) executes end-to-end.

```bash
python reproduce.py --mode smoke
```

Expected output: `[OK] Smoke test passed.`  Outputs are written to `runs/smoke/`.

---

### Mode 3: Single-cell search  *(30 min – 4 h)*

Run the paper's best-performing configuration for one problem with a reduced iteration budget.
This demonstrates the search process but will not necessarily reach the paper's record value in a
short run — the best construction appears after a median of 64–97% of the full budget.

```bash
# Unit-square stabbing — paper's 20/13 configuration (200 iterations ≈ 30–60 min)
python reproduce.py --mode single --problem unit_square --iterations 200

# MISR — paper's 3/2 configuration
python reproduce.py --mode single --problem misr --iterations 200

# Guillotine — paper's 1/3 configuration
python reproduce.py --mode single --problem guillotine --iterations 200
```

To run at a larger budget (approaching the paper's results), increase `--iterations`:

```bash
# Longer run — several hours
python reproduce.py --mode single --problem unit_square --iterations 5000
```

Each problem's best cell runs with the settings of its own cohort (see Mode 5): MISR and guillotine
use n = 8, grid 8, population 32, elite 6 and training every 7 generations; unit-square uses n = 20,
grid 16, population 32, elite 12, initial pool 128, 4 immigrants and training every 10.  By default each
run starts from a fresh random seed, so results vary from run to run.  To replay the original run, use the
seed recorded for this cell with `--paper-seeds` (or choose a seed with `--seed N`):

```bash
python reproduce.py --mode single --problem unit_square --paper-seeds --iterations 250
```

The recorded seeds and settings of all 81 original runs are in
`docs/assets/replacement_81_final_20260712/data/final_81_seeds.json`.  A seed with matching settings is
intended for replay, but results can differ across library versions, hardware and thread counts.  The
unit-square record (20/13) first appeared at generation 190 in the original run; the MISR and guillotine
records appeared after about 3.1 and 5.8 hours on the original hardware.

Results are written to `runs/single_<problem>/`, and the exact cell is recorded in
`runs/single_<problem>/best_cell.jsonl`.  A summary CSV and audit JSON are generated
automatically at the end.

**Best components per problem (Table 1–3 in the paper):**

| Problem | Representation | Local search | Surrogate | Target |
|---------|---------------|--------------|-----------|--------|
| MISR | `triangle_free_rect` | `sequence_pair_pivot` | `exact_lp_gap_pressure` | gap 3/2 |
| Unit-square | `sqstab_exact_grid` | `symmetry_crossover_hillclimb` | `exact_stab_gap_pressure` | gap 20/13 |
| Guillotine | `rect_direct_disjoint` | `witness_breaking` | `depth_limited_dp` | fraction 1/3 |

---

### Mode 4: Figure and table regeneration  *(< 2 minutes)*

Regenerate all analysis figures and LaTeX table fragments from the committed CSV data.

```bash
python reproduce.py --mode figures
```

Outputs are written to:
- `docs/assets/replacement_81_final_20260712/analysis/` — PNG figures
- `docs/assets/replacement_81_final_20260712/report/`   — LaTeX macro files

This requires `matplotlib` and `pandas` (`pip install -r requirements-analysis.txt`).

To also rebuild the full PDF report (requires a LaTeX installation):

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -cd docs/manuscript/patternboost_81_run_analysis.tex
```

---

### Mode 5: Full 81-cell matrix  *(~2 000 CPU-hours — HPC recommended)*

Reproduce the complete experiment matrix.  This runs all 81 configurations in sequence or in
parallel.

The paper's final 81 cells were assembled from three runtime cohorts, and the matrix used here
(`runs/final_81_matrix.jsonl`, written by `--mode full` or by `multilevel.cli final-81-matrix`)
gives each cell its own cohort's settings:

| Cohort | Cells | Settings |
|--------|------:|----------|
| Retained (July 9) | 36 | n = 8, grid 8, population 32, elite 6, training every 7 generations |
| Replacement (July 11) | 42 | MISR/guillotine n = 12, grid 8; unit-square n = 20, grid 16; population 16, elite 4, training every 10 |
| Unit-square resolution follow-up | 3 | n = 20, grid 16, population 32, elite 12, initial pool 128, 4 immigrants/generation, resolution islands; training every 10 |

All cohorts use exact scoring every 5 generations, 16 model samples, 3 model epochs, block size 128,
a 24 h wall-clock budget and a cap of 10^6 generations.  The cohort rule reproduces `source_cohort` and
`population_size` in `docs/assets/replacement_81_final_20260712/data/final_81_runs.csv` for all 81 rows.
(`multilevel.cli matrix --stage main` generates the original 81-cell design, which does not contain the
replacement cells, so it is not the paper's final table.)

```bash
# Sequential (very slow — for testing only)
python reproduce.py --mode full --iterations 1000000

# Parallel on a multicore machine (N = number of parallel cells)
python reproduce.py --mode full --iterations 1000000 --parallel 8
```

**For cluster/HPC execution**, use the built-in Slurm array generator:

```bash
# 1. Generate the paper's final 81-cell matrix (each cell carries its own cohort's settings)
PYTHONPATH=src python3 -m multilevel.cli final-81-matrix \
  --budget-seconds 86400 \
  --out runs/final_81_matrix.jsonl

# 2. Generate a Slurm array script (runs up to 10^6 generations or the 24 h budget)
PYTHONPATH=src python3 -m multilevel.cli make-slurm \
  --matrix runs/final_81_matrix.jsonl \
  --out scripts/main_81_array.slurm \
  --project-dir "$PWD" \
  --results-dir runs/main_81_hpc \
  --time 25:00:00 \
  --partition compute \
  --cpus-per-task 4 \
  --mem 16G \
  --runner patternboost

# 3. Submit
sbatch scripts/main_81_array.slurm

# 4. After completion, collect and audit
PYTHONPATH=src python3 -m multilevel.cli summary \
  --root runs/main_81_hpc --out runs/main_81_hpc/summary.csv

PYTHONPATH=src python3 -m multilevel.cli audit \
  --summary runs/main_81_hpc/summary.csv \
  --out runs/main_81_hpc/audit/audit.json \
  --csv runs/main_81_hpc/audit/audit.csv
```

**Expected results** (from the paper's 81-cell matrix):

| Problem | Best exact score | Configuration |
|---------|-----------------|---------------|
| MISR | **1.500** (= 3/2) | `triangle_free_rect / sequence_pair_pivot / exact_lp_gap_pressure` |
| Unit-square stabbing | **1.538** (= 20/13) | `sqstab_exact_grid / symmetry_crossover_hillclimb / exact_stab_gap_pressure` |
| Guillotine | **0.333** (= 1/3) | `rect_direct_disjoint / witness_breaking / depth_limited_dp` |

Unless `--paper-seeds` is given, each run starts from a fresh random seed, so exact scores may differ
from the paper.  The paper ran each cell exactly once with no repeated-seed axis; the committed
certificates are the primary evidence, and certificate verification (Mode 1) is the definitive
reproducibility check.  `--mode full --paper-seeds` uses the recorded seed of every cell.

---

## Repository Layout

```
reproduce.py                          ← this reproduction script
ARTIFACT_EVALUATION.md                ← this guide
README.md                             ← developer README
requirements.txt                      ← NumPy + SciPy (core)
requirements-torch.txt                ← + PyTorch (transformer)
requirements-analysis.txt             ← + matplotlib, pandas (figures)
environment.yml                       ← Conda environment (Python 3.11)
pyproject.toml                        ← package metadata
src/multilevel/                       ← Python package + CLI
  cli.py                              ← all CLI subcommands
  patternboost.py                     ← PatternBoost search loop
  components.py                       ← 3×3×3 component registry
  representations.py                  ← instance encodings
  mutations.py                        ← local-search operators
  surrogates.py                       ← surrogate scoring functions
  modeling.py                         ← n-gram + transformer training
  scorers/
    misr.py                           ← MISR exact LP + ILP oracle
    unit_square.py                    ← stabbing LP + set-cover oracle
    guillotine.py                     ← guillotine DP oracle
  audit.py                            ← certificate batch verifier
  canonical.py                        ← JSON hash utilities
  render.py                           ← SVG certificate renderer
examples/                             ← tiny instances for smoke tests
  misr_small.json
  unit_square_small.json
  guillotine_small.json
scripts/                              ← helper scripts (HPC, analysis)
  make_main_matrix.sh
  run_smoke.sh
  run_one_cell.sh
  plot_main_matrix_analysis.py
  generate_main_matrix_tex.py
  *.slurm                             ← Slurm array templates
docs/assets/replacement_81_final_20260712/
  run_artifacts/                      ← 81 best-certificate JSON files (one per cell)
  data/                               ← final_81_runs.csv, epoch history CSV
  analysis/                           ← pre-generated PNG figures
  audit/                              ← pre-run audit.json and audit.csv
  report/                             ← pre-generated LaTeX fragments
docs/manuscript/
  patternboost_81_run_analysis.tex    ← full report LaTeX source
  patternboost_81_run_analysis.pdf    ← compiled report PDF
runs/                                 ← local run outputs (git-ignored)
```

---

## CLI Reference

The main CLI is `PYTHONPATH=src python3 -m multilevel.cli <subcommand>`.

```
registry                   Print all registered component choices
matrix                     Generate the 81-row experiment matrix JSONL
score <problem> <file>     Score one instance with the exact oracle
verify <cert.json>         Re-verify a certificate
render <cert.json>         Render a certificate to SVG
smoke                      Score and verify all bundled examples
patternboost-cell          Run one PatternBoost cell from a matrix
summary                    Collect run outputs into a CSV
audit                      Batch re-verify certificates
make-slurm                 Generate a Slurm array script for HPC
```

Full help for any subcommand:

```bash
PYTHONPATH=src python3 -m multilevel.cli patternboost-cell --help
```

---

## Certificate Format

Each certificate is a JSON file with the following fields.

**MISR certificate (`misr_certificate_v1`):**
```json
{
  "schema": "misr_certificate_v1",
  "rectangles": [[x1, x2, y1, y2], ...],
  "alpha_int": 4,
  "alpha_lp": 6.0,
  "score": 1.5,
  "maximal_cliques": [[0, 3, 7], ...],
  "integer_solution": [0, 4, 9],
  "solver_status": "optimal",
  "certificate_hash": "sha256:..."
}
```

**Unit-square stabbing certificate (`unit_square_stab_certificate_v1`):**
```json
{
  "schema": "unit_square_stab_certificate_v1",
  "squares": [[x, y], ...],
  "critical_lines": {"vertical": [...], "horizontal": [...]},
  "tau_int": 4,
  "tau_lp": 2.6,
  "score": 1.5384...,
  "integer_lines": ["v3", "h5", ...],
  "solver_status": "optimal",
  "certificate_hash": "sha256:..."
}
```

**Guillotine certificate (`guillotine_certificate_v1`):**
```json
{
  "schema": "guillotine_certificate_v1",
  "rectangles": [[x1, x2, y1, y2], ...],
  "n": 9,
  "saved": 6,
  "destroyed": 3,
  "score": 0.3333...,
  "dp_states": 512,
  "optimal_strategy": {...},
  "solver_status": "optimal",
  "certificate_hash": "sha256:..."
}
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'multilevel'`**  
Activate the virtual environment and run `pip install -e . -r requirements.txt`.

**`ModuleNotFoundError: No module named 'torch'`**  
PyTorch is optional.  Either install it (`pip install -r requirements-torch.txt`) or use
`--model-kind ngram` in single-cell runs.  The smoke test and certificate verification do not need
PyTorch.

**Certificate verification fails for one or more files**  
This should not happen with the committed certificates.  If it does, please open a GitHub issue
with the full output of:
```bash
PYTHONPATH=src python3 -m multilevel.cli verify <failing_cert.json>
```

**The single-cell run is slow**  
The `exact_lp_gap_pressure` and `exact_stab_gap_pressure` surrogates solve the full LP at every
ranking step, which is expensive.  This is intentional: these are the most effective surrogates.
Reduce `--iterations` for a faster run, or switch to a cheaper surrogate by picking a different
matrix row.

**Running on Windows**  
All Python code is cross-platform.  The `.sh` helper scripts in `scripts/` require bash (Git Bash
or WSL on Windows).  The `reproduce.py` script is pure Python and works on all platforms.

`--mode full --parallel N` is **not supported on Windows**: Windows antivirus/Defender briefly
locks newly created temp files, causing the atomic checkpoint rename (`os.replace`) to fail under
parallel workers.  Use `--parallel 1` on Windows, or run on Linux / WSL / HPC for parallel
execution.

---

## Contact

For questions about the artifact, please open an issue on the anonymous repository.
