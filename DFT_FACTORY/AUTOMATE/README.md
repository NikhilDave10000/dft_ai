# DFT Data Factory — Complete Usage Guide

## Repository Layout

```
dft_factory/
├── config/
│   └── factory_config.py     # Single source of truth — edit FACTORY_ROOT here
├── core/
│   ├── dir_init.py            # Step 1: Create iteration directory tree
│   ├── orch_run.py            # Step 2: Launch tool run + monitor + harvest
│   ├── harvest.py             # Step 3: Normalize outputs (auto-called by orch_run)
│   └── lifecycle.py           # Step 4: Tagging, CSV aggregation, trash purge
├── tcl/
│   └── TMAX/
│       └── ATPG_SAF.tcl       # TCL body — no hardcoded paths, Python injects all vars
├── tools/
│   └── env_gate.sh            # Tool environment switcher (licenses, paths)
└── notebooks/                 # Jupyter analysis notebooks (add your own)
```

---

## One-Time Setup

1. Edit `config/factory_config.py`:
   - Set `FACTORY_ROOT` to your dedicated directory
   - Fill in real binary paths and license servers in `TOOL_REGISTRY`

2. Make scripts executable:
   ```bash
   chmod +x core/*.py tools/env_gate.sh
   ```

3. Add to your shell (optional, for convenience):
   ```bash
   export DFT_FACTORY=/your/path/dft_factory
   export PYTHONPATH=$DFT_FACTORY:$PYTHONPATH
   ```

---

## Full Run — Step by Step

### Step 1: Initialize the iteration directory

```bash
python core/dir_init.py \
    --design  i2c       \
    --tool    TMAX      \
    --stage   ATPG_SAF  \
    --exp     EXP1      \
    --sub     1.1       \
    --iter    Iter_01   \
    --fault-type SAF    \
    --notes  "baseline SAF, default settings"
```

Preview without creating anything:
```bash
python core/dir_init.py ... --dry-run
```

Auto-increment iteration number:
```bash
python core/dir_init.py ... --iter auto
```

This creates:
```
FACTORY_ROOT/i2c/TMAX/ATPG_SAF/EXP1/1.1/Iter_01/
    ├── .metadata        ← JSON tracking file
    ├── config/          ← TCL scripts actually used
    ├── inputs/          ← symlinks only (heavy files)
    ├── scripts/         ← merged launcher script
    ├── work/            ← tool scratchpad (wiped after harvest)
    ├── logs/            ← passported log transcripts
    ├── reports/         ← phase-prefixed .rpt files
    ├── database/        ← binary tool state
    └── outputs/         ← patterns, fault lists
```

---

### Step 2: Run the experiment

```bash
python core/orch_run.py \
    --iter-path FACTORY_ROOT/i2c/TMAX/ATPG_SAF/EXP1/1.1/Iter_01 \
    --netlist   /path/to/i2c_dc_scan_insertion.vg                 \
    --libs      /path/to/gen.v                                     \
    --tcl       tcl/TMAX/ATPG_SAF.tcl
```

orch_run.py will:
1. Source `env_gate.sh TMAX` (sets license + PATH)
2. Symlink netlist + libs into `inputs/`
3. Inject config header into TCL → write merged script to `scripts/`
4. Launch `tmax -f scripts/run_Iter_01.tcl` in the `work/` dir
5. Stream logs live to terminal AND `logs/`
6. On exit, auto-call `harvest.py`
7. Update `.metadata` with final status + runtime

To rerun (fix a script error, same folder):
```bash
python core/orch_run.py --iter-path ... --rerun
```

To skip harvest (debugging):
```bash
python core/orch_run.py --iter-path ... --no-harvest
```

---

### Step 3: Harvest (if not auto-called)

```bash
python core/harvest.py --iter-path FACTORY_ROOT/i2c/TMAX/ATPG_SAF/EXP1/1.1/Iter_01
```

Keeps `work/` for debugging:
```bash
python core/harvest.py --iter-path ... --no-wipe-work
```

---

### Step 4: Tag iterations

```bash
# Mark a passing run as the reference
python core/lifecycle.py --tag GOLDEN \
    --iter-path FACTORY_ROOT/i2c/TMAX/ATPG_SAF/EXP1/1.1/Iter_03

# Mark failed/unwanted runs for deletion
python core/lifecycle.py --tag TRASH \
    --iter-path FACTORY_ROOT/i2c/TMAX/ATPG_SAF/EXP1/1.1/Iter_01
```

---

### Step 5: View all iterations

```bash
# All iterations for one design
python core/lifecycle.py --list --scope FACTORY_ROOT/i2c

# All iterations factory-wide
python core/lifecycle.py --list
```

---

### Step 6: Build trend analysis CSV

```bash
python core/lifecycle.py --build-csv \
    --scope  FACTORY_ROOT/i2c \
    --output FACTORY_ROOT/analysis/i2c_trends.csv
```

The CSV has columns: design, tool, stage, exp_id, sub_exp, iter_id, status,
fault_coverage_pct, total_patterns, runtime_s, tool_version, and more.
Load into pandas/Excel/Jupyter for analysis.

---

### Step 7: Reclaim disk space

```bash
# Preview what would be deleted
python core/lifecycle.py --purge-trash --scope FACTORY_ROOT/i2c --dry-run

# Delete for real
python core/lifecycle.py --purge-trash --scope FACTORY_ROOT/i2c
```

---

## Adding a New Experiment (e.g. vary EDT channels)

```bash
# Sub-experiment 1.2 = same EXP, different config
python core/dir_init.py --design i2c --tool TMAX --stage ATPG_SAF \
    --exp EXP1 --sub 1.2 --iter Iter_01 \
    --notes "4 EDT channels vs 2 in 1.1"

python core/orch_run.py \
    --iter-path FACTORY_ROOT/i2c/TMAX/ATPG_SAF/EXP1/1.2/Iter_01 \
    --netlist   /path/to/netlist.vg \
    --libs      /path/to/gen.v
```

---

## Adding a New Design

No code changes needed. Just use a different `--design` value:

```bash
python core/dir_init.py --design spi --tool TMAX --stage ATPG_SAF \
    --exp EXP1 --sub 1.1 --iter Iter_01
```

---

## Adding a New Tool (e.g. Tessent)

1. Add entry to `TOOL_REGISTRY` in `factory_config.py`
2. Add environment block to `tools/env_gate.sh`
3. Add TCL body at `tcl/TESSENT/ATPG_SAF.tcl` (or whichever stage)
4. Add harvest rules for the new tool in `HARVEST_RULES`

---

## TCL Variable Reference (injected by orch_run.py)

| Variable      | Example value                              |
|---------------|--------------------------------------------|
| `$DESIGN`     | `i2c`                                      |
| `$TOOL`       | `TMAX`                                     |
| `$STAGE`      | `ATPG_SAF`                                 |
| `$EXP_ID`     | `EXP1`                                     |
| `$SUB_EXP`    | `1.1`                                      |
| `$ITER_ID`    | `Iter_01`                                  |
| `$RUN_TAG`    | `i2c__TMAX__ATPG_SAF__EXP1__1.1__Iter_01` |
| `$LOG_DIR`    | `FACTORY_ROOT/.../Iter_01/logs`            |
| `$RPT_DIR`    | `FACTORY_ROOT/.../Iter_01/reports`         |
| `$OUT_DIR`    | `FACTORY_ROOT/.../Iter_01/outputs`         |
| `$WORK_DIR`   | `FACTORY_ROOT/.../Iter_01/work`            |
| `$INPUT_DIR`  | `FACTORY_ROOT/.../Iter_01/inputs`          |
| `$DB_DIR`     | `FACTORY_ROOT/.../Iter_01/database`        |
| `$PHASE_SETUP`| `10_BUILD-T`                               |
| `$PHASE_DRC`  | `20_DRC-T`                                 |
| `$PHASE_FAULT`| `30_FAULT`                                 |
| `$PHASE_ENGINE`| `40_TEST-T`                               |
| `$PHASE_SIM`  | `60_SIM`                                   |
| `$PHASE_EXPORT`| `80_EXPORT`                               |

---

## .metadata JSON Reference

```json
{
  "status":          "PASS",
  "lock":            false,
  "iter_tag":        "GOLDEN",
  "tool":            "TMAX",
  "tool_version":    "2024.03",
  "stage":           "ATPG_SAF",
  "exp_id":          "EXP1",
  "sub_exp":         "1.1",
  "iter_id":         "Iter_01",
  "design":          "i2c",
  "fault_type":      "SAF",
  "timestamp_start": "2025-06-01T09:00:00+00:00",
  "timestamp_end":   "2025-06-01T10:23:11+00:00",
  "runtime_s":       4991,
  "phase_completed": [10, 20, 30, 40, 80],
  "parent_iter":     null,
  "harvest_done":    true,
  "notes":           "baseline SAF"
}
```
