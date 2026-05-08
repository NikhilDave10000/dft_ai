Here is the exhaustive, production-ready documentation file for your STIL procedure. You can save this exact text as a `.md` (Markdown) file and keep it in your DFT Factory repository as the definitive reference for this specific I2C design.

---

# DFT STIL Protocol Reference: `i2c_master_top`
**Design:** `i2c_master_top`  
**Source:** DFT Compiler R-2020.09-SP5-5  
**STIL Version:** IEEE 1450.0 (Extension 2005)  
**Generated:** Wed Apr 8 12:11:14 2026  

---

## 1. General Waveform Character (WFC) Reference Table
*Per IEEE 1450 Standard & Synopsys TestMAX Interpretation*

| WFC | Category | Interpretation & ATE Behavior | DFT / CAD Context |
| :--- | :--- | :--- | :--- |
| **`0`** | Drive | Drive-low (Force Logic 0) for the entire waveform. | Used for static pin assignments. |
| **`1`** | Drive | Drive-high (Force Logic 1) for the entire waveform. | Used for static pin assignments (e.g., holding Test Mode high). |
| **`D`** | Drive | Drive Down (Force 0). Often the start of a waveform event. | Base state for active-low signals. |
| **`U`** | Drive | Drive Up (Force 1). Opposite of D. | Base state for active-high signals. |
| **`Z`** | Drive | Drive-inactive (High Impedance). Disconnects ATE driver. | **Critical** for bidirectional pins to prevent bus contention. |
| **`N`** | Drive | Drive-unknown / No Change. ATE does not alter voltage. | Used in Condition (`C {}`) blocks to leave pins floating/uncontrolled to save ATE vector time. |
| **`P`** | Event | Active Pulse. Executes the `P` waveform defined in the Timing block (e.g., D->U->D). | **Strictly for clocks.** Drives the launch/capture/shift edges. |
| **`D`** *(cmd)* | Event | Drive two active pulses. | **Strictly for Path-Delay MUX operation.** Not used in standard Transition Delay. |
| **`E`** *(cmd)* | Event | Drive early active pulse (matches 1st pulse of `D`). | **Strictly for Path-Delay MUX operation.** |
| **`H`** | Measure | Compare-High (Expect 1). Strobe at specified offset. | If measured value is 0, ATE triggers a fail. |
| **`L`** | Measure | Compare-Low (Expect 0). Strobe at specified offset. | If measured value is 1, ATE triggers a fail. |
| **`T`** | Measure | Compare-Toggle / Inactive. Expects a transition or safe state. | Often used for masking or specific bus states. |
| **`X`** | Measure | Compare-Mask / Don't Care. ATE inhibits comparison. | Used during shift, or to mask unstable/unknown logical states. |

---

## 2. Signal & Architecture Mapping

### 2.1 Functional Interfaces
The design utilizes a standard Wishbone interface for processor communication and an I2C interface for external serial communication.
*   **Wishbone Inputs:** `wb_clk_i`, `wb_rst_i`, `wb_adr_i[0:2]`, `wb_dat_i[0:7]`, `wb_cyc_i`, `wb_stb_i`, `wb_we_i`.
*   **Wishbone Outputs:** `wb_ack_o`, `wb_dat_o[0:7]`, `wb_inta_o`.
*   **I2C Interface:** `scl_pad_i/o`, `sda_pad_i/o`. 
*   **I2C Output Enables:** `scl_padoen_o`, `sda_padoen_o`. (Active-low to disable internal drivers and let external pins pull the bus).

### 2.2 DFT Port Sharing Strategy (Scan Output Consolidation)
To save physical die area and pins, DFT Compiler utilized **Scan Output Sharing**. 
*   Dedicated scan inputs (`test_si1` through `test_si5`) are provided.
*   Dedicated scan outputs are **missing** `test_so3` and `test_so5`.
*   **The Mapping:**
    *   Chain 3 Scan Out is routed to functional pin `sda_padoen_o`.
    *   Chain 5 Scan Out is routed to functional pin `wb_inta_o`.
*   *CAD Impact:* During `load_unload`, the ATPG tool must ensure that the functional logic driving `sda_padoen_o` and `wb_inta_o` is disabled, otherwise the scan data will collide with functional data.

---

## 3. Scan Chain Architecture

The design utilizes a **5-Chain Flat Scan Architecture**. All chains share a global control infrastructure.

| Chain Name | Scan In | Scan Out | Length (Bits) | Scan Enable | Master Clock |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `"1"` | `test_si1` | `test_so1` | 31 | `test_se` | `wb_clk_i` |
| `"2"` | `test_si2` | `test_so2` | 31 | `test_se` | `wb_clk_i` |
| `"3"` | `test_si3` | `sda_padoen_o` | 31 | `test_se` | `wb_clk_i` |
| `"4"` | `test_si4` | `test_so4` | 30 | `test_se` | `wb_clk_i` |
| `"5"` | `test_si5` | `wb_inta_o` | 30 | `test_se` | `wb_clk_i` |

*   **Longest Chain:** 31 bits. The ATPG engine will pad Chains 4 and 5 with dummy shift cycles to match this length during the `Shift` procedure.
*   **Clock Dependency:** All chains are strictly dependent on `wb_clk_i`. `arst_i` is declared in the `_clk` group but is treated as an asynchronous control; it is **not** pulsed during the `Shift` procedure (due to the `1P` positional mapping, see Section 5).

---

## 4. Timing Analysis & WaveformTables (WFT)

The STIL file defines **5 distinct WaveformTables**, all sharing an identical 100ns (10MHz) period. 

### 4.1 Base Timing Definitions
*   **Period:** `100ns` (Safe, slow ATE frequency).
*   **Input Drive:** All inputs (`0`, `1`, `Z`, `N`) drive at `0ns`.
*   **Output Measure Strobe:** All outputs (`H`, `L`, `T`, `X`) are masked (`X`) until `40ns`. At `40ns`, the ATE captures the value. Because `40ns` is before the clock edge (`45ns`), this is a **Pre-Clock Measure** protocol.
*   **System Clock (`wb_clk_i`):** Active-high pulse. Drives Low (`D`) at `0ns`, High (`U`) at `45ns`, Low (`D`) at `55ns`. (Pulse width = 10ns).
*   **Async Reset (`arst_i`):** Active-low pulse. Drives High (`U`) at `0ns`, Low (`D`) at `45ns`, High (`U`) at `55ns`.

### 4.2 The "Placeholder" WFTs
The file contains `_multiclock_capture_WFT_`, `_allclock_capture_WFT_`, `_allclock_launch_WFT_`, and `_allclock_launch_capture_WFT_`. 
*   **Observation:** DFT Compiler generated these as empty clones of `_default_WFT_`.
*   **Purpose:** These are structural placeholders required by TestMAX to prevent V4 DRC errors when specific ATPG modes (like Broadside or LOC) are invoked via TCL (`set_delay -launch_cycle system_clock`).
*   **CAD Action Required:** For actual At-Speed Transition Delay testing, a TCL script (like the LOC factory script) *must* use `update_clock` to mathematically inject the 20ns at-speed squeeze (e.g., 85ns/5ns) into the `_allclock_launch` and `_allclock_capture` tables. Without this, at-speed testing will occur at the slow 10MHz shift frequency.

---

## 5. Procedural Execution Flow

### 5.1 Macro: `test_setup`
Executed once at the beginning of the test program.
*   **Timing:** Uses `_default_WFT_`.
*   **Condition (`C {}`):** `"all_inputs" = \r25 N` (Leaves all 25 inputs uncontrolled/No Change). `"all_outputs" = \r17 X` (Masks all outputs).
*   **Vector 1:** Forces `arst_i = 1` (Inactive/High) and `wb_clk_i = 0` (Off/Low).
*   **Vector 2:** Empty vector `V {}`. Acts as a 100ns settling delay to let the reset propagate electrically through the chip.

### 5.2 Procedure: `load_unload` (Shift Control)
Executed to load stimulus into the scan chains and unload captured responses.
*   **Timing:** Uses `_default_WFT_`.
*   **Condition (`C {}`):** Forces `1NNNNN0 \r18 N` (25 chars = 25 inputs). This hardcodes `arst_i` to `1`, `wb_clk_i` to `0`, and leaves the rest as `N` (No change).
*   **Pre-Shift Vector:** `V { "test_se" = 1; }`. Explicitly asserts the Scan Enable pin high before shifting begins.
*   **The `Shift` Loop:** 
    *   **Vector:** `V { "_clk" = 1P; "_si" = \r5 #; "_so" = \r5 #; }`
    *   **Positional Mapping Magic (`1P`):** The `_clk` group is defined as `"arst_i" + "wb_clk_i"`. The string `1P` maps character-by-character: `arst_i` receives `1` (held static High), and `wb_clk_i` receives `P` (executes the 45-55ns pulse). This guarantees the reset does not pulse during shift.
    *   **Data Injection:** `\r5 #` repeats the data variable `#` 5 times, injecting one bit for each of the 5 scan chains.
*   *CAD Note:* The STIL file lacks explicit bidirectional (`Z`-state) forcing for the I2C pads during shift. If simulation mismatches occur, a CAD engineer must manually add `scl_pad_i = Z; sda_pad_i = Z;` to the Pre-Shift vector.

### 5.3 Procedures: Capture Variations
The STIL provides 4 capture procedures. All use identical timing and data structures, differing only in their naming convention.
*   **`multiclock_capture`, `allclock_capture`, `allclock_launch`, `allclock_launch_capture`**
*   **Structure:**
    1.  `C {}` block applies the `1NNNNN0` background state.
    2.  Single `V {}` vector forces Primary Inputs (`_pi = \r25 #`) and measures Primary Outputs (`_po = \r17 #`) simultaneously in the same cycle.
*   **LOC vs LOS Reality:** Despite their names, TestMAX ATPG operates on *how the TCL script configures the engine*, not the STIL procedure name. If the TCL script calls `set_delay -launch_cycle system_clock`, TestMAX will internally parse these procedures and inject the necessary launch/capture separation using the underlying WFTs.