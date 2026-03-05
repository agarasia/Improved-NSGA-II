# Improved-NSGA-II

Two new implementations of XP26 (accepted) work: variants of NSGA-II for test–requirement selection with a time budget.

This document explains how to run the full pipeline: **experiments** → **accumulate results** → **plot comparison** → **descriptive statistics** → **box plots**.

---

## Experimental setup

The experiments reported in this repository were run on this computer:

| Item | Spec |
|------|------|
| **Machine** | MacBook Air |
| **Chip** | Apple M3 |
| **CPU** | 8 cores (4 Performance, 4 Efficiency) |
| **Memory** | 8 GB |
| **OS** | macOS 26.3 (Darwin 25.3.0) |

---

## Prerequisites

- **Python 3** (tested with 3.x)
- **Libraries**: `pandas`, `openpyxl`, `matplotlib`, `seaborn`

Install with:

```bash
pip install pandas openpyxl matplotlib seaborn
```

---

## Input data

- **Datasets** live in `datasets/` (e.g. `D1.xlsx`, `D2.xlsx`).
- Each Excel file must contain columns that can be mapped to: `tc_id`, `us_id`, `tc_executiontime`, `us_businessvalue` (the pipeline converts Excel to CSV internally).
- For D2, test execution data can be produced as described in `pipeline/generating_test_execution_data_for_D2.md`. The user story mappings to the test cases can be found [here](https://gitlab.com/SEMERU-Code-Public/Data/icse20-comet-data-replication-package/-/blob/main/LibEST/req_to_test_ground.txt?ref_type=heads).


---

## Pipeline overview

| Step | Script | Purpose |
|------|--------|--------|
| 1 | `pipeline_runner.py` | Run NSGA-II experiments (30 reps × budgets × K values × 3 algorithms) |
| 2 | `result_accumulate.py` | Aggregate per-run CSVs into summary CSVs per algorithm/K |
| 3 | `plot_results.py` | Plot comparison line charts (budget vs HV, BV, coverage, time) |
| 4 | `generate_descriptive_statistics.py` | Compute descriptive stats and write an Excel workbook |
| 5 | `generate_boxplots.py` | Generate box plots of metric distributions per K |

All pipeline scripts use **relative paths** for inputs and outputs. Where you run them from (and optional config edits) is described below.

---

## 1. Run the experiments

**What it does:** Converts the dataset Excel to CSV, then runs three NSGA-II variants (`NSGA-II-1.py`, `NSGA-II-2.py`, `NSGA-II-3.py`) for:

- **30 repetitions** per configuration  
- **Budget levels:** 10%, 20%, …, 90% of total test time  
- **K / G levels:** K ∈ {1500, 3500, 5500, 7500, 9500} (and for NSGA-II-1, corresponding G values 7, 17, 27, 37, 47)  
- **Population size:** 200  

For each (algorithm, budget%, K) it writes one CSV with per-seed metrics plus an `AVERAGE` row (e.g. `experiment_results/nsga_ii_1_1500/NSGA-II-1_budget10_K1500.csv`).

**Where to run:** The runner calls `python3 NSGA-II-1.py` (etc.) and expects the Excel (or its path) in the current directory. So run it from **`source_code/`** and point the config at the dataset.

**Configuration** (at top of `pipeline/pipeline_runner.py`):

- `INPUT_EXCEL` — path to the dataset Excel (e.g. `'../datasets/D1.xlsx'` when run from `source_code/`).
- `BASE_OUTPUT_DIR` — where to write `experiment_results/` (e.g. `'../experiment_results'` to put results at repo root).

**Command:**

```bash
cd source_code
python3 ../pipeline/pipeline_runner.py
```

For **D2**, set `INPUT_EXCEL = '../datasets/D2.xlsx'` (and optionally `BASE_OUTPUT_DIR = '../experiment_results_D2'` if you want a separate folder). Then run the same command from `source_code/`.

---

## 2. Accumulate results

**What it does:** Reads the per-budget CSVs under `experiment_results/` (e.g. `nsga_ii_1_1500/`, `nsga_ii_2_1500/`, …), takes the `AVERAGE` row from each, and writes one **summary** CSV per (algorithm, K), e.g. `summary_NSGA-II-1_K1500.csv`, with columns like `budget_pct`, `hv`, `total_BV`, `pct_req_covered`, `wall_clock_time`.

**Where to run:** From the **repository root**, so that `experiment_results` is the folder produced in Step 1 (or set `BASE_DIR` to that folder).

**Configuration** (at top of `pipeline/result_accumulate.py`):

- `BASE_DIR` — directory containing the `nsga_ii_*` subfolders (default: `'experiment_results'`). Use e.g. `'experiment_results_D2'` if you used a different output dir for D2.

**Command:**

```bash
# From repo root
python3 pipeline/result_accumulate.py
```

---

## 3. Plot comparison results

**What it does:** For each K, loads the summary CSVs for all three algorithms and draws a **2×2 line plot** (budget % vs Hypervolume, Total Business Value, Requirement Coverage %, Execution Time). Saves one PNG per K: `comparison_K1500.png`, `comparison_K3500.png`, etc.

**Where to run:** From the **repository root** (or the directory that contains `BASE_DIR`).

**Configuration** (at top of `pipeline/plot_results.py`):

- `BASE_DIR` — same as in Step 2 (default: `'experiment_results'`).

**Command:**

```bash
# From repo root
python3 pipeline/plot_results.py
```

Outputs are written in the current directory (e.g. `comparison_K1500.png`). You can move them into something like `results/experiment_results/D1/` or `D2/` for organization.

---

## 4. Descriptive statistics

**What it does:** Scans the **raw run** CSVs (excluding the `AVERAGE` row) for each (algorithm, K, budget %) and computes mean, std, median, min, max for `hv`, `total_BV`, and `pct_req_covered`. Writes one Excel file with one sheet per algorithm: `Experiment_Descriptive_Statistics.xlsx`.

**Where to run:** From the **repository root**.

**Configuration** (at top of `pipeline/generate_descriptive_statistics.py`):

- `BASE_DIR` — same as in Step 2 (default: `'experiment_results'`).
- `OUTPUT_FILE` — output Excel name (default: `'Experiment_Descriptive_Statistics.xlsx'`). For D1/D2 you can use e.g. `'results/descriptive_statistics/D1/D1_Descriptive_Statistics.xlsx'` if you create that path.

**Command:**

```bash
# From repo root
python3 pipeline/generate_descriptive_statistics.py
```

---

## 5. Box plots

**What it does:** For each K, collects the raw runs (again excluding `AVERAGE`) for all algorithms and budget levels and draws **three box plots** (one per metric: Hypervolume, Total Business Value, Requirement Coverage %). Saves one PNG per K: `boxplot_K1500.png`, …, `boxplot_K9500.png`.

**Where to run:** From the **repository root**.

**Configuration** (at top of `pipeline/generate_boxplots.py`):

- `BASE_DIR` — same as in Step 2 (default: `'experiment_results'`).

**Command:**

```bash
# From repo root
python3 pipeline/generate_boxplots.py
```

As with comparison plots, you can copy the generated `boxplot_K*.png` files into e.g. `results/descriptive_statistics/D1/` or `D2/`.

---

## Quick reference: run order and commands

From a **fresh experiment** for one dataset (e.g. D1):

1. **Experiments** (from `source_code/`, with `INPUT_EXCEL` and `BASE_OUTPUT_DIR` set):
   ```bash
   cd source_code && python3 ../pipeline/pipeline_runner.py
   ```

2. **Accumulate, plot, stats, box plots** (from repo root, with `BASE_DIR` pointing at the same `experiment_results` folder):
   ```bash
   python3 pipeline/result_accumulate.py
   python3 pipeline/plot_results.py
   python3 pipeline/generate_descriptive_statistics.py
   python3 pipeline/generate_boxplots.py
   ```

For **D2**, change `INPUT_EXCEL` (and optionally `BASE_OUTPUT_DIR`) in `pipeline_runner.py`, then set `BASE_DIR` in the other four scripts to the same output directory (e.g. `experiment_results_D2`) and run the same commands.

---

## Output layout (typical)

After a full run you will have:

- **`experiment_results/`** (or your custom name):  
  - `nsga_ii_1_1500/`, `nsga_ii_2_1500/`, … with per-budget CSVs and `summary_NSGA-II-*_K*.csv`.
- **Comparison plots:** `comparison_K1500.png`, …, `comparison_K9500.png`.
- **Descriptive statistics:** `Experiment_Descriptive_Statistics.xlsx` (or your custom path).
- **Box plots:** `boxplot_K1500.png`, …, `boxplot_K9500.png`.

The repo’s `results/` folder (e.g. `results/experiment_results/D1/`, `results/descriptive_statistics/D1/`) is one possible place to copy these for D1/D2 organization.
