# BESS thermal/cooling scenario 02

Scope: compare cooling operation across the four models. Cycling degradation is retained as a secondary result; economic assessment is excluded.

Pipeline prepared for another machine. No real 30-day PMP solve or production
thermal/cooling run has been executed. Unit tests use controlled fixtures; the
integration test substitutes a BVP stub.

## Run on another machine

Copy this entire folder, including `8.2022`, `inputs` and Python modules.
Use Python 3.13 (see `environment_snapshot.json`), then:

```powershell
python -m pip install -r requirements.txt
```

Open `30days_scenario_02.ipynb`, select this environment, restart the kernel and
run all seven cells from the top. All thermal/cooling parameters are in cell 1.
The electrical solver can take hours. Alternatively, from this folder:

```powershell
python run_scenario.py --prepare-only  # inputs/paths only; no PMP or thermal simulation
python run_scenario.py --run           # full pipeline, including four original PMP solvers
```

## Notebook cells

1. Central thermal/cooling/weather configuration and isolated run directory.
2. Original PMP functions, copied byte-for-byte from the baseline function cell.
3. Original electrical/data setup with new ambient input and local output path.
4. Original continuous 30-day PMP solve, unchanged, with checkpoint resume.
5. Existing comparison/dispatch/cycling assessment plus new exact thermal model.
6. Cooling/temperature/energy/duty/activation reports and plots.
7. Original/copy integrity audit.

## Final parameters

| Parameter | Value | Unit |
|---|---:|---|
| G | 0.05 | kg/s |
| Cp | 4.180 | kJ/(kg K) |
| Ts | 25 | degC |
| Ton | 32 | degC |
| Toff | 29 | degC |
| COP | 2 | thermal/electrical energy ratio |
| C (unchanged) | 600 | kJ/K |
| r (unchanged) | 2 | K/kW |
| r_bat (unchanged) | 0.013 | ohm |
| V_nom (unchanged) | 400 | V |
| Thermal/control step | 900 | seconds (confirmed 15 minutes) |
| Electrical step (unchanged) | 1800 | seconds |

An input guard rejects changes to the four preserved pack parameters. Cp is
converted to 4180 J/(kg K), C to 600000 J/K, and r to 0.002 K/W internally.
Battery heat is I^2*r_bat in W. Cooling electrical power is thermal power/COP.

## Hysteresis and numerical integration

At each 15-minute interval start, T>=32 C commands ON, T<=29 C commands OFF,
and temperatures between 29 and 32 C retain the previous command. Initial
command is OFF; initial temperature remains the first Tamb value. OFF-to-ON
commands are counted, including t=0 if it commands ON. No new command is
counted at the zero-duration terminal node.

The physical ODE is unchanged (kW and kJ/K):

```text
C*dT/dt = I^2*r_bat/1000 + (Tamb-T)/r + u*G*Cp*(Ts-T)
```

The implementation converts to W/J and uses the analytical solution and the
analytical temperature integral for each 900-second interval with held power,
Tamb and cooling command. Heat extraction varies with temperature inside an
interval; exported mean power integrates to exact interval energy. Cooling is
not switched at an internal threshold crossing. OFF heat/electricity are zero.

## Thirty distinct weather days

`inputs/reference_ambient_2days.csv` holds the original reference pair. Odd days
reference day 1; even days reference day 2. For Tamb strictly greater than 32 C,
their original durations are 3 h and 4.5 h. Each new day is constrained to its
corresponding reference +/- 1 h. The scenario has shorter and longer periods,
daytime-shape/amplitude/phase variations, smooth noise and a consecutive-step
jump bound. Seed 20261108 makes it reproducible. This is synthetic weather,
not measured meteorological data. Durations use half-hour sample holds,
matching the original thermal forcing convention.

## Time coverage and aging

Electrical/SOC results remain 1440 nodes from 0 to 719.5 h. Thermal/control has
2880 intervals and 2881 temperature nodes from 0 to 720 h. The last power and
Tamb sample are held for the final half-hour, as confirmed. Every day has
exactly 96 thermal intervals and 24 hours.

Cycling degradation retains the unchanged Xu module and original SOC nodes:
rainflow runs once on the full electrical history, with the new temperature
sampled at those nodes. No fictitious SOC at 720 h is appended. Initial SOH
remains 90%; calendar aging is excluded; inherited LMO parameters are not a
validated LFP calibration.

## Output isolation and resume

```text
30days_scenario_02/
  30days_scenario_02.ipynb
  scenario_thermal.py / scenario_weather.py / scenario_project.py / scenario_outputs.py
  battery_cycling_degradation.py  # unchanged local copy
  8.2022/                       # unchanged copied datasets
  inputs/                       # reference weather and preserved parameter snapshot
  runs/scenario02_ef1b5703b8f6/
    configuration.json
    inputs/ambient_30days.csv
    inputs/ambient_daily_validation.csv
    inputs/Ambient_scenario_30days.png/pdf
    30days_results/Model_*_results_30days.xlsx
    30days_results/*checkpoint.json
    30days_results/assessment/Assessment_30days.xlsx
    30days_results/assessment/cooling_energy/
      Cooling_energy_30days.xlsx
      Thermal_control_30days.png/pdf
      Cooling_energy_30days.png/pdf
      Cooling_daily_operation_30days.png/pdf
      Battery_temperature_statistics_30days.png/pdf
      Final_report.json / Final_report.md
    validation/integrity_audit.json
```

The notebook explicitly uses `runs/scenario02_ef1b5703b8f6/`. Cells 1 and 4
create that directory when absent; code edits no longer create new run names.
Cell 4 skips each model whose `Model_<model>_results_30days.xlsx` already
exists in its `30days_results/` directory. Only missing models are solved.
Checkpoints, signatures and convergence labels are not required for skipping;
the saved convergence labels are retained. An unreadable existing result stops
the cell instead of triggering a solve over that file. This reuse rule does
not certify that imported results match later changes to settings or inputs.
The existing `configuration.json` is retained as the record of the original
run; same-run plots/reports can be regenerated. Original workspace files are
never overwritten.

Original PMP acceptance/report logic is retained; new-weather convergence has
not been evaluated. Cooling is offline and its electricity is not fed back to
dispatch. G*Cp*(T-Ts) retains the original ideal heat-exchange assumption. No
separate fan/pump/standby load or equipment capacity cap is modeled.

## Files and validation

`original_integrity_manifest.json` records original/copied SHA-256 hashes;
`original_integrity_check.json` records the preparation-machine audit.
`requirements.txt` records package versions; the Python installation itself
is not copied. Supporting copied simulation modules have not been modified.

New implementation files: `scenario_thermal.py`, `scenario_weather.py`,
`scenario_project.py`, `scenario_outputs.py`, `run_scenario.py`,
`verify_original_files.py` and the new notebook. The inherited aging module
remains intact. The notebook contains its PMP functions and solver code;
running it does not require the old notebooks or their results.

```powershell
python verify_original_files.py  # original machine only
```

The `test_*.py` files and their compiled caches were removed from this scenario
at the user's request. They are not required to run the simulation. Earlier
validation results remain documented in `PREPARATION_REPORT.md`; those checks
used a BVP stub and were not a convergence audit. Runtime validation and
`verify_original_files.py` remain available.

On another machine, copied-reference hashes are checked locally; paths to the
preparation machine's originals are not treated as local originals.

Original-workspace changes are reported rather than blocking execution, as
confirmed by the user. Changed/missing scenario input/reference copies still
block execution. Existing weather CSVs are compared by numeric content and
schema, tolerating line-ending differences and serialization rounding; they
are never overwritten. Newly written weather CSVs use explicit LF newlines.

The unneeded copied economic module and its test were removed from this scenario only.
Their original workspace files remain unchanged; exclusions are recorded in the integrity manifest.

The unused `battery_assessment.py`, `Battery_assessment_31_32.ipynb`,
`reference_original/` copies and `build_notebook.py` were also removed at the
user's request. New-scenario results under `runs/` were preserved. The integrity
manifest checks only the remaining required copies. `PREPARATION_REPORT.md`
is a historical preparation record, not the current file inventory.

The two preparation-only runs `scenario02_6899e9f98e44` and
`scenario02_c896bdec5336` were removed at the user's request. The complete
`scenario02_ef1b5703b8f6` results and checkpoints were retained.

Cell 3 reloads weather helpers before input loading, including when only that cell is rerun in an existing kernel.

## Single-column figures and selected-day detail

`scenario_plot_style.py` centralizes the 3.5-inch figure width, serif fonts,
embedded PDF fonts and 600-dpi PNG export. PDF/PNG saves retain the physical
canvas size instead of cropping the page width. The five-panel dispatch figure
is 8.2 inches high to keep its panels readable; other figures use shorter
single-column layouts. Styling does not modify simulation data or calculations.

Cell 5 ranks the 30 days by the maximum high-ambient absolute battery-power
peak across all four models. It selects rank 2 (earlier day first for ties),
prints all four selected-day peaks and shaving values, and exports the ranking
to `Day_peak_ranking` in `Assessment_30days.xlsx`. Subplot 5 shows that full day;
its inset selects an actual sign transition in I/III with II/IV resting at the
same sample. It omits the inset if no such sample exists. The standalone
day-12 plot is no longer generated.

`Battery_temperature_30days.png/.pdf` is a separate full-720-hour temperature
figure. Cycling damage, capacity loss and SOH are exported as three separate figures;
the cooling-control figure contains ON/OFF status, thermal power and electrical
power. The underlying thermal and degradation results are unchanged.

Figure readability update: `IEEE_HEIGHT_SCALE=1.30` increases all figure heights without changing the 3.5-inch width. Base text is 7.5 pt; ticks/legends are 6.5 pt. Subplot 5 now uses a smaller fixed 17..18 h inset on the selected day.

Daily resting time, abrupt transitions and peak shaving share one three-panel figure (`Daily_resting_abrupt_shaving_30days`). The separate cycling figures are `Cycling_damage_30days`, `Cycling_capacity_loss_30days` and `Battery_soh_30days` (PDF/PNG).

The dispatch and daily-comparison figures have independent final height settings in cell 5: `ASSESS30_MAIN_FIGURE_HEIGHT_IN=8.2` and `ASSESS30_DAILY_FIGURE_HEIGHT_IN=5.8`. Their widths remain 3.5 inches; these two heights are not multiplied by the shared height scale.

Total cooling heat and total cooling electricity are separate figures: `Cooling_heat_total_30days` and `Cooling_electricity_total_30days`. Daily/cumulative electricity remain together in `Cooling_energy_trends_30days`. Numeric accounting is unchanged.

Individual height reductions: battery temperature uses 2/3 of its previous height; cycling capacity loss and total cooling electricity each use 1/2. Width, fonts, data and all other figure sizes are unchanged.
