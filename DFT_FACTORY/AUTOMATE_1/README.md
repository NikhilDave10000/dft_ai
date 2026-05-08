# DFT Data Factory

## Directory structure

```
/project_root
└── /<DESIGN_NAME>               # e.g. i2c_master
    └── /<TOOL_SUITE>            # SYNOPSYS | TESSENT
        └── /<DFT_STAGE>         # SCAN | ATPG | SIM
            └── /<EXP_ID>        # e.g. SA_EXP1
                └── /<SUB_EXP_ID># e.g. E1.1
                    └── /<ITER_ID>   # iter_001, iter_002...
                        ├── .metadata
                        ├── config/
                        ├── inputs/     ← soft links only
                        ├── scripts/    ← physical copies
                        ├── logs/       ← 10_BUILD-T_run.log
                        ├── reports/    ← 40_TEST-T_coverage.rpt
                        ├── database/
                        ├── outputs/
                        └── work/       ← wiped after harvest
```

## File map

```
dft_factory/
├── config/
│   └── factory_config.py   ← edit once: FACTORY_ROOT + tool paths
├── core/
│   ├── utils.py             ← shared helpers (don't run directly)
│   ├── dir_init.py          ← Step 1: create iteration tree
│   ├── orch_run.py          ← Step 2: launch tool run
│   ├── harvest.py           ← Step 3: normalize outputs (auto-called)
│   └── lifecycle.py         ← Step 4: tag / list / CSV
├── tools/
│   └── env_gate.sh          ← csh environment switcher
└── tcl/
    ├── SYNOPSYS/            ← place your .tcl scripts here
    └── TESSENT/             ← place your .do scripts here
```

---

## One-time setup

```bash
# 1. Set your root path
nano config/factory_config.py    # set FACTORY_ROOT

# 2. Make scripts executable
chmod +x core/*.py tools/env_gate.sh
```

---

## Every-run workflow

### Step 1 — Create the iteration

```bash
python core/dir_init.py \
    --design i2c_master \
    --tool   SYNOPSYS   \
    --stage  ATPG       \
    --exp    SA_EXP1    \
    --sub    E1.1       \
    --iter   iter_001   \
    --note   "baseline SAF, default settings"

# Auto-number:  --iter auto
# Preview only: --dry-run
```

### Step 2 — Run your experiment

```bash
python core/orch_run.py \
    --iter-path $FACTORY_ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001 \
    --tcl       /path/to/your_atpg_script.tcl \
    --netlist   /path/to/netlist.vg \
    --libs      /path/to/cells.v \
    --spf       /path/to/design.spf
```

orch_run.py will:
- Source `env_gate.sh SYNOPSYS` (mirrors your manual `csh` step)
- Symlink netlist/libs/spf into `inputs/`
- Prepend a config header to your TCL (injects `$LOG_DIR`, `$RPT_DIR`, `$PHASE_*` etc.)
- Launch `csh -c "tmax -f run_iter_001.tcl"` from the `work/` directory
- Stream output live to terminal + `logs/`
- Auto-call harvest.py on exit

To rerun a failed script (same folder):
```bash
python core/orch_run.py --iter-path ... --tcl ... --rerun
```

### Step 3 — Tag your results

```bash
python core/lifecycle.py --tag GOLDEN --iter-path .../iter_003
python core/lifecycle.py --tag TRASH  --iter-path .../iter_001
```

### Step 4 — View all iterations

```bash
python core/lifecycle.py --list --scope $FACTORY_ROOT/i2c_master
```

### Step 5 — Build trend CSV

```bash
python core/lifecycle.py --build-csv --scope $FACTORY_ROOT/i2c_master
# writes: $FACTORY_ROOT/i2c_master/analysis/trend_analysis.csv
```

### Step 6 — Reclaim disk space

```bash
python core/lifecycle.py --purge-trash --dry-run   # preview
python core/lifecycle.py --purge-trash --scope $FACTORY_ROOT/i2c_master
```

---

## TCL variables injected by orch_run.py

Your TCL script receives these variables automatically — no hardcoding needed:

| Variable       | Example                                        |
|----------------|------------------------------------------------|
| `$DESIGN`      | `i2c_master`                                   |
| `$TOOL_SUITE`  | `SYNOPSYS`                                     |
| `$STAGE`       | `ATPG`                                         |
| `$EXP_ID`      | `SA_EXP1`                                      |
| `$SUB_EXP_ID`  | `E1.1`                                         |
| `$ITER_ID`     | `iter_001`                                     |
| `$RUN_TAG`     | `i2c_master__SYNOPSYS__ATPG__SA_EXP1__E1.1__iter_001` |
| `$LOG_DIR`     | `.../iter_001/logs`                            |
| `$RPT_DIR`     | `.../iter_001/reports`                         |
| `$OUT_DIR`     | `.../iter_001/outputs`                         |
| `$WORK_DIR`    | `.../iter_001/work`                            |
| `$INPUT_DIR`   | `.../iter_001/inputs`                          |
| `$DB_DIR`      | `.../iter_001/database`                        |
| `$PHASE_SETUP` | `10_BUILD-T`  (SYNOPSYS) / `10_SETUP` (TESSENT)|
| `$PHASE_DRC`   | `20_DRC-T`    / `20_ANALYSIS`                  |
| `$PHASE_FAULT` | `30_FAULT`    / `30_FAULT-MODEL`               |
| `$PHASE_ENGINE`| `40_TEST-T`   / `40_ATPG`                      |
| `$PHASE_SIM`   | `60_SIM`      / `60_SIMULATION`                |
| `$PHASE_EXPORT`| `80_EXPORT`   / `80_EXPORT`                    |

Use `$PHASE_*` vars in `wrpt` calls so report names are always consistent:
```tcl
wrpt $PHASE_ENGINE coverage {report_faults -summary -verbose}
# writes: reports/40_TEST-T_coverage.rpt
```

---

## Adding a new DFT stage

```bash
python core/dir_init.py \
    --add-stage MBIST \
    --stage-desc "Memory BIST insertion" \
    --stage-phases "10,20,25,40,80" \
    --stage-chain-from SCAN
```

That's it — one command, no other file needs editing.

---

## Adding a new tool suite

Edit `config/factory_config.py` → `TOOL_REGISTRY` (add one dict entry).
Edit `tools/env_gate.sh` → add one `case` block.
Drop your `.tcl`/`.do` file in `tcl/<TOOLNAME>/`.

---

## .metadata reference

```json
{
  "status":           "PASS",
  "lock":             false,
  "iter_tag":         "GOLDEN",
  "design":           "i2c_master",
  "tool_suite":       "SYNOPSYS",
  "stage":            "ATPG",
  "exp_id":           "SA_EXP1",
  "sub_exp_id":       "E1.1",
  "iter_id":          "iter_001",
  "experiment_note":  "baseline SAF",
  "tool_version":     "2024.03",
  "timestamp_start":  "2025-06-01T09:00:00+00:00",
  "timestamp_end":    "2025-06-01T10:23:00+00:00",
  "runtime_s":        4980,
  "phases_completed": [10, 20, 30, 40, 80],
  "parent_iter":      null,
  "harvest_done":     true
}
```
