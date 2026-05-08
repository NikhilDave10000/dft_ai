# DFT Factory — Unified Automation Architecture

This is the consolidated DFT automation engine, merged from AUTOMATE through
AUTOMATE_3 into a single coherent structure.

## Directory Layout

```
dft_factory/
├── config/
│   └── factory_config.py     # Single source of truth — edit FACTORY_ROOT here
├── core/
│   ├── utils.py             # Shared helpers (meta read/write, phase tools)
│   ├── dir_init.py         # Step 1: Create iteration directory tree
│   ├── orch_run.py         # Step 2: Launch tool + monitor + harvest
│   ├── harvest.py          # Step 3: Normalize outputs (auto-called)
│   └── lifecycle.py        # Step 4: Tag, list, purge, trend CSV
├── tcl/
│   └── SYNOPSYS/
│       ├── _factory_helpers.tcl   # TCL helper block (wrpt, wlog, wdb, wout)
│       ├── ATPG_SAF.tcl          # Generic TetraMAX ATPG flow body
│       └── ATPG_SAF_EXP1.1.tcl  # Experiment-specific flow (EXP1.1)
├── tools/
│   └── env_gate.sh            # Tool environment switcher (licenses, PATH)
├── notebooks/                  # Jupyter analysis notebooks (user-created)
└── README.md
```

## What Changed vs the AUTOMATE Iterations

| Area | AUTOMATE | AUTOMATE_1 | AUTOMATE_2 | AUTOMATE_3 | Unified |
|------|-----------|-------------|------------|------------|---------|
| Structure | Flat files | Flat, utils.py added | TCL experiments | Enhanced core | **Structured dirs** |
| Config | `TOOL_REGISTRY` (TMAX/TESSENT) | Renamed to SYNOPSYS/TESSENT, added shell/launch flags | — | — | **config/factory_config.py** |
| Metadata | `METADATA_SCHEMA` | Renamed to `METADATA_DEFAULTS`, keys renamed (`tool`→`tool_suite`) | — | — | **config/factory_config.py** |
| Shared code | — | **utils.py** (new) | — | — | **core/utils.py** |
| dir_init | Basic | Added `--add-stage`, `--list-stages` | — | — | **core/dir_init.py** |
| orch_run | Basic | csh wrapper, TCL header injection | — | **Added --sdc, --timing, --layout, --extras, --top-module, --inject K=V** | **core/orch_run.py** (v3) |
| harvest | Basic | Phase inference, passport | — | **Added --extra-search-dirs, --phase-map, enhanced KPI regex** | **core/harvest.py** (v2) |
| lifecycle | Basic KPIs | Added filtering | — | **Added --filter-status, --filter-tag, --filter-design** | **core/lifecycle.py** (v3) |
| TCL helpers | — | — | **_factory_helpers.tcl** (new) | — | **tcl/SYNOPSYS/_factory_helpers.tcl** |
| TCL experiments | ATPG_SAF.tcl | — | **ATPG_SAF_EXP1.1.tcl** (new) | — | **tcl/SYNOPSYS/ATPG_SAF_EXP1.1.tcl** |

## Quick Start

### One-time setup
1. Edit `config/factory_config.py` — set `FACTORY_ROOT` (or set env var `DFT_FACTORY_ROOT`)
2. Update binary paths and license servers in `config/factory_config.py`
3. Source `tools/env_gate.sh SYNOPSYS` (or TESSENT) before running

### Create an iteration
```bash
python core/dir_init.py \
    --design  i2c_master \
    --tool    SYNOPSYS \
    --stage   ATPG \
    --exp     SA_EXP1 \
    --sub     E1.1 \
    --iter    auto
```

### Run the experiment
```bash
python core/orch_run.py \
    --iter-path <path-from-dir_init> \
    --tcl       tcl/SYNOPSYS/ATPG_SAF.tcl \
    --netlist   /path/to/netlist.vg \
    --libs      /path/to/cells.v
```

### Tag results
```bash
python core/lifecycle.py --tag GOLDEN --iter-path <path>
python core/lifecycle.py --build-csv --scope dft_factory
```

## Key Design Decisions

1. **config/ is the single source of truth** — no hardcoded paths anywhere else
2. **core/utils.py is the base layer** — all other core scripts import from it
3. **TCL helpers are sourced, not rewritten** — `source tcl/SYNOPSYS/_factory_helpers.tcl`
4. **Phase index system** — numeric IDs (10, 20, 30...) with per-tool mode strings
5. **Iteration lineage** — `parent_iter` tracks --rerun ancestry
6. **Passport system** — every log gets a self-describing header block
