#!/usr/bin/env python3
"""
Artifact reproduction script for:
  "Towards Learning-Guided Discovery of Extremal Geometric Constructions:
   A PatternBoost Study"

This script provides five evaluation modes with increasing time requirements:

  verify   Re-verify the 81 committed certificates (< 5 minutes).
  smoke    Run the built-in smoke test on small examples (< 5 minutes).
  single   Run one PatternBoost search cell with a reduced iteration budget
           (30 min – 4 h depending on problem and hardware).
  figures  Regenerate the analysis figures and LaTeX tables from committed
           data CSVs (< 2 minutes; requires matplotlib and pandas).
  full     Run all 81 cells at the paper's full budget
           (~2 000 CPU-hours; intended for HPC clusters).

Usage:
  python reproduce.py --mode verify
  python reproduce.py --mode smoke
  python reproduce.py --mode single [--problem misr|unit_square|guillotine] [--iterations 200]
  python reproduce.py --mode figures
  python reproduce.py --mode full [--iterations 1000000] [--parallel N]

No commercial solver license is required.  All exact oracles use only
open-source components bundled with or installed alongside this repository:
  - HiGHS LP solver via SciPy (scipy.optimize.linprog)
  - Custom branch-and-bound integer solvers (src/multilevel/scorers/)
  - Custom dynamic-programming guillotine solver (src/multilevel/scorers/)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _python() -> str:
    return sys.executable


def _run(cmd: list[str], *, check: bool = True) -> int:
    env = os.environ.copy()
    python_path = str(SRC)
    if "PYTHONPATH" in env:
        python_path += os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = python_path
    result = subprocess.run(cmd, env=env)
    if check and result.returncode != 0:
        print(
            f"\n[ERROR] Command failed (exit {result.returncode}):\n  " + " ".join(cmd),
            file=sys.stderr,
        )
        sys.exit(result.returncode)
    return result.returncode


def _cli(*args: str) -> list[str]:
    return [_python(), "-m", "multilevel.cli", *args]


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_python() -> None:
    vi = sys.version_info
    if vi < (3, 10):
        print(
            f"[ERROR] Python 3.10+ required; found {vi.major}.{vi.minor}.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[OK] Python {vi.major}.{vi.minor}.{vi.micro}")


def check_install() -> None:
    try:
        import multilevel  # noqa: F401
    except ModuleNotFoundError:
        print(
            "[ERROR] The 'multilevel' package is not installed.\n"
            "  Run:  pip install -e . -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    print("[OK] multilevel package found")


def check_torch() -> bool:
    try:
        import torch  # noqa: F401
        print("[OK] PyTorch found — transformer-guided sampling enabled")
        return True
    except ModuleNotFoundError:
        print(
            "[INFO] PyTorch not found.  The n-gram fallback sampler will be used instead.\n"
            "       To enable the transformer, run:  pip install -r requirements-torch.txt"
        )
        return False


def check_analysis_deps() -> bool:
    missing = []
    for pkg in ("matplotlib", "pandas"):
        try:
            __import__(pkg)
        except ModuleNotFoundError:
            missing.append(pkg)
    if missing:
        print(
            f"[WARN] Missing packages for figure generation: {', '.join(missing)}\n"
            "       Install with:  pip install -r requirements-analysis.txt"
        )
        return False
    print("[OK] matplotlib and pandas found")
    return True


# ---------------------------------------------------------------------------
# Mode: verify
# ---------------------------------------------------------------------------

def mode_verify() -> None:
    """Re-verify all committed certificates using the artifact mapping."""
    print("\n=== MODE: verify ===")
    print("Re-verifying committed best-certificate JSON files.")
    print("Each file is re-scored from scratch by the exact oracle.\n")

    cert_root = (
        ROOT / "docs" / "assets" / "replacement_81_final_20260712" / "run_artifacts"
    )
    mapping_csv = cert_root / "artifact_mapping.csv"

    if not cert_root.exists():
        print(
            f"[ERROR] Certificate directory not found:\n  {cert_root}\n"
            "        Ensure the complete repository is present.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Use the artifact mapping CSV when present; fall back to glob.
    if mapping_csv.exists():
        import csv
        entries: list[tuple[str, Path]] = []
        with mapping_csv.open(newline="") as f:
            for row in csv.DictReader(f):
                config_id = row["config_id"]
                cert_rel = row.get("certificate_path", "").strip()
                if cert_rel:
                    entries.append((config_id, cert_root / cert_rel))
        print(f"Loaded {len(entries)} entries from artifact_mapping.csv\n")
    else:
        # Fallback: find all JSON files inside certificates/ subdirectories.
        raw = sorted(cert_root.rglob("best_iter*.json"))
        entries = [(str(p.relative_to(cert_root)), p) for p in raw]
        print(f"Found {len(entries)} certificate files (mapping CSV not found).\n")

    passed, failed, skipped = 0, 0, 0
    for config_id, cert_path in entries:
        if not cert_path.exists():
            skipped += 1
            print(f"  [SKIP]  {config_id}  (no certificate — trivial or no improvement)")
            continue
        rel = cert_path.relative_to(ROOT)
        rc = _run(_cli("verify", str(cert_path)), check=False)
        if rc == 0:
            passed += 1
            print(f"  [PASS]  {config_id}")
        else:
            failed += 1
            print(f"  [FAIL]  {config_id}  ({rel})")

    total = passed + failed + skipped
    print(f"\n{'='*55}")
    print(
        f"Verification: {passed} passed, {failed} failed, {skipped} skipped "
        f"(no certificate) out of {total}"
    )
    if failed:
        print("[ERROR] Certificate(s) failed re-verification.", file=sys.stderr)
        sys.exit(1)
    print("[OK] All present certificates verified.")


# ---------------------------------------------------------------------------
# Mode: smoke
# ---------------------------------------------------------------------------

def mode_smoke() -> None:
    """Score and verify one small example per problem using the exact oracles."""
    print("\n=== MODE: smoke ===")
    print("Running the built-in smoke test (score + verify per problem).\n")

    out = ROOT / "runs" / "smoke"
    out.mkdir(parents=True, exist_ok=True)

    # Also individually score the bundled examples to confirm the exact solvers work.
    examples = ROOT / "examples"
    for problem in ("misr", "unit_square", "guillotine"):
        ex = examples / f"{problem}_small.json"
        if ex.exists():
            cert = out / f"{problem}_small_cert.json"
            print(f"  Scoring {ex.name}...")
            _run(_cli("score", problem, str(ex), "--out", str(cert)))
            print(f"  Verifying {cert.name}...")
            _run(_cli("verify", str(cert)))

    print("\n  Running built-in smoke command (score + verify per problem)...")
    _run(_cli("smoke", "--out", str(out)))

    print(f"\n[OK] Smoke test passed.  Outputs in {out.relative_to(ROOT)}/")


# ---------------------------------------------------------------------------
# Mode: single
# ---------------------------------------------------------------------------

# Best component combinations from the paper (final 81-cell table).  The runtime
# parameters come from multilevel.components (the settings the paper's runs used).
BEST_CONFIGS = {
    "misr": {
        "representation": "triangle_free_rect",
        "local_search":   "sequence_pair_pivot",
        "surrogate":      "exact_lp_gap_pressure",
        "target": "integrality gap 3/2 = 1.500",
    },
    "unit_square": {
        "representation": "sqstab_exact_grid",
        "local_search":   "symmetry_crossover_hillclimb",
        "surrogate":      "exact_stab_gap_pressure",
        "target": "integrality gap 20/13 ~ 1.538",
    },
    "guillotine": {
        "representation": "rect_direct_disjoint",
        "local_search":   "witness_breaking",
        "surrogate":      "depth_limited_dp",
        "target": "destroyed fraction 1/3 ~ 0.333",
    },
}


def _final_81_rows() -> list[dict]:
    """The paper's final 81 cells, each with its own cohort's runtime settings.

    Not `multilevel.cli matrix --stage main` (original design only).  See
    `multilevel.components.build_final_81_matrix` for the cohort rules.
    """
    from multilevel.components import build_final_81_matrix

    return build_final_81_matrix()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8"
    )


def _find_matrix_index(rows: list[dict], problem: str, cfg: dict) -> int:
    """Return the index of the row matching the problem and the three components."""
    keys = ("representation", "local_search", "surrogate")
    for i, row in enumerate(rows):
        if row.get("problem") == problem and all(row.get(k) == cfg[k] for k in keys):
            return i
    sys.exit(
        f"[ERROR] No matrix row for problem={problem} "
        + " ".join(f"{k}={cfg[k]}" for k in keys)
    )


def mode_single(problem: str, iterations: int, has_torch: bool) -> None:
    """Run the paper's best-scoring configuration for one problem."""
    cfg = BEST_CONFIGS[problem]
    print(f"\n=== MODE: single (problem={problem}) ===")
    print(
        "Best configuration from the paper: "
        f"{cfg['representation']} / {cfg['local_search']} / {cfg['surrogate']}"
    )
    print(f"Paper-reported target: {cfg['target']}")
    print(f"Iterations: {iterations}  (paper used ~1 000 000 over 24 h)\n")
    print(
        "Note: A short run will typically find non-trivial constructions but may not\n"
        "      reach the paper's best value — the best appears after a median of\n"
        "      64–97% of the total budget.\n"
    )

    out_root = ROOT / "runs" / f"single_{problem}"
    out_root.mkdir(parents=True, exist_ok=True)

    rows = _final_81_rows()
    idx = _find_matrix_index(rows, problem, cfg)
    matrix_file = out_root / "best_cell.jsonl"
    _write_jsonl(matrix_file, [rows[idx]])
    print(f"[INFO] Wrote single-cell matrix {matrix_file.relative_to(ROOT)}")
    print(f"[INFO] Cell: {rows[idx]['run_id']}")

    model_kind = "auto" if has_torch else "ngram"

    _run(
        _cli(
            "patternboost-cell",
            "--matrix", str(matrix_file),
            "--index", "0",
            "--out-root", str(out_root),
            "--iterations", str(iterations),
            "--exact-every", "5",
            "--train-every", "10",
            "--model-samples", "16",
            "--model-kind", model_kind,
            "--model-epochs", "3",
            "--block-size", "128",
            "--checkpoint-every", "1",
        )
    )

    # Collect and audit.
    summary_csv = out_root / "summary.csv"
    _run(_cli("summary", "--root", str(out_root), "--out", str(summary_csv)))

    audit_dir = out_root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _run(
        _cli(
            "audit",
            "--summary", str(summary_csv),
            "--out", str(audit_dir / "audit.json"),
            "--csv", str(audit_dir / "audit.csv"),
        )
    )

    print(f"\n[OK] Done.  Results in {out_root.relative_to(ROOT)}/")
    print(f"     Summary:  {(out_root / 'summary.csv').relative_to(ROOT)}")
    print(f"     Audit:    {(audit_dir / 'audit.csv').relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Mode: figures
# ---------------------------------------------------------------------------

def mode_figures() -> None:
    """Regenerate analysis figures and LaTeX tables from the committed CSVs."""
    print("\n=== MODE: figures ===")
    print("Regenerating figures and LaTeX tables from committed data.\n")

    base = ROOT / "docs" / "assets" / "replacement_81_final_20260712"
    data_dir = base / "data"
    analysis_dir = base / "analysis"
    report_dir = base / "report"
    audit_csv = base / "audit" / "audit.csv"

    if not data_dir.exists():
        print(f"[ERROR] Data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    analysis_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    print("[1/2] Generating figures...")
    _run(
        [_python(), str(ROOT / "scripts" / "plot_main_matrix_analysis.py"),
         str(data_dir), "--out-dir", str(analysis_dir)]
    )

    print("[2/2] Generating LaTeX tables...")
    _run(
        [_python(), str(ROOT / "scripts" / "generate_main_matrix_tex.py"),
         str(data_dir),
         "--plot-table-dir", str(analysis_dir),
         "--audit-csv", str(audit_csv),
         "--out-dir", str(report_dir)]
    )

    print(f"\n[OK] Figures:  {analysis_dir.relative_to(ROOT)}/")
    print(f"     LaTeX:    {report_dir.relative_to(ROOT)}/")


# ---------------------------------------------------------------------------
# Mode: full
# ---------------------------------------------------------------------------

def _run_cell(args: tuple) -> tuple[int, int]:
    """Top-level worker for ProcessPoolExecutor (must be picklable)."""
    idx, matrix_file, out_root, iterations, model_kind = args
    rc = _run(
        _cli(
            "patternboost-cell",
            "--matrix", str(matrix_file),
            "--index", str(idx),
            "--out-root", str(out_root),
            "--iterations", str(iterations),
            "--model-kind", model_kind,
            "--checkpoint-every", "1",
        ),
        check=False,
    )
    return idx, rc


def mode_full(iterations: int, parallel: int, has_torch: bool) -> None:
    """Run all 81 PatternBoost cells (HPC-scale)."""
    print("\n=== MODE: full ===")
    print(
        f"Running all 81 cells, {iterations} iterations each.\n"
        f"Paper used ~1 000 000 iterations over 24 h per cell on 4-core nodes.\n"
    )
    if sys.platform == "win32" and parallel > 1:
        print(
            "[WARN] Parallel mode is not supported on Windows: atomic file rename\n"
            "       (os.replace) is blocked by antivirus on temp checkpoint files.\n"
            "       Use --parallel 1 on Windows, or run on Linux / WSL / HPC.\n"
        )
    if iterations >= 100_000 and parallel < 4:
        print(
            "[WARN] High iteration count with few parallel workers will take many days.\n"
            "       See README.md for HPC/Slurm instructions for cluster submission.\n"
        )

    matrix_file = ROOT / "runs" / "final_81_matrix.jsonl"
    print("[INFO] Generating the paper's final 81-cell matrix...")
    _write_jsonl(matrix_file, _final_81_rows())

    with matrix_file.open() as f:
        n_rows = sum(1 for _ in f)
    print(f"[INFO] Matrix: {n_rows} rows.\n")

    out_root = ROOT / "runs" / "full_matrix"
    out_root.mkdir(parents=True, exist_ok=True)
    model_kind = "auto" if has_torch else "ngram"

    cell_args = [
        (i, matrix_file, out_root, iterations, model_kind) for i in range(n_rows)
    ]

    if parallel > 1:
        import concurrent.futures
        print(f"[INFO] Running {n_rows} cells with {parallel} workers...\n")
        with concurrent.futures.ProcessPoolExecutor(max_workers=parallel) as pool:
            futs = {pool.submit(_run_cell, ca): ca[0] for ca in cell_args}
            for fut in concurrent.futures.as_completed(futs):
                try:
                    idx, rc = fut.result()
                    tag = "OK" if rc == 0 else f"FAILED rc={rc}"
                except Exception as exc:
                    idx = futs[fut]
                    tag = f"CRASHED ({exc})"
                print(f"  [{tag}] cell {idx}")
    else:
        for ca in cell_args:
            idx, rc = _run_cell(ca)
            print(f"[INFO] Cell {idx}/{n_rows - 1}... {'OK' if rc == 0 else f'FAILED rc={rc}'}")

    print("\n[INFO] Collecting summary and auditing...")
    summary_csv = out_root / "summary.csv"
    _run(_cli("summary", "--root", str(out_root), "--out", str(summary_csv)))
    audit_dir = out_root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _run(
        _cli(
            "audit",
            "--summary", str(summary_csv),
            "--out", str(audit_dir / "audit.json"),
            "--csv", str(audit_dir / "audit.csv"),
        )
    )
    print(f"\n[OK] Full-matrix run complete.  Results in {out_root.relative_to(ROOT)}/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--mode",
        choices=["verify", "smoke", "single", "figures", "full"],
        required=True,
        help=(
            "verify: re-verify committed certificates (< 5 min);  "
            "smoke: built-in test (< 5 min);  "
            "single: one search cell (30 min – 4 h);  "
            "figures: regenerate figures from committed CSVs (< 2 min);  "
            "full: all 81 cells (~2 000 CPU-hours)."
        ),
    )
    p.add_argument(
        "--problem",
        choices=["misr", "unit_square", "guillotine"],
        default="unit_square",
        help="Problem for --mode single (default: unit_square).",
    )
    p.add_argument(
        "--iterations",
        type=int,
        default=None,
        help=(
            "Search iterations per cell.  Default: 200 for --mode single (~30-60 min); "
            "1 000 000 for --mode full (paper budget, 24 h per cell).  "
            "Pass an explicit value to override."
        ),
    )
    p.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Parallel worker processes for --mode full (default: 1).",
    )
    p.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip Python-version and package checks.",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    print("=" * 62)
    print("PatternBoost Geometric Extremal Search — Artifact Reproduction")
    print("=" * 62 + "\n")

    if not args.skip_checks:
        check_python()
        check_install()
    has_torch = check_torch()
    print()

    if args.mode == "verify":
        mode_verify()

    elif args.mode == "smoke":
        mode_smoke()

    elif args.mode == "single":
        mode_single(args.problem, args.iterations if args.iterations is not None else 200, has_torch)

    elif args.mode == "figures":
        if not check_analysis_deps():
            print(
                "[ERROR] Install analysis dependencies first:\n"
                "        pip install -r requirements-analysis.txt",
                file=sys.stderr,
            )
            sys.exit(1)
        mode_figures()

    elif args.mode == "full":
        iters = args.iterations if args.iterations is not None else 1_000_000
        mode_full(iters, args.parallel, has_torch)


if __name__ == "__main__":
    main()
