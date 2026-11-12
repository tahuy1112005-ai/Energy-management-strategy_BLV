# BESS thermal/cooling scenario 02

The project now uses one notebook and one Python support file:

```text
30days_scenario_02/
  30days_scenario_02.ipynb    # Parameters, original PMP functions/solver, assessment calls
  bess_pipeline.py          # Weather, thermal/cooling, cycling, plots, paths, audits, CLI
  project_metadata.json     # Consolidated environment, provenance, guards and inventories
  8.2022/                   # Original copied load/PV datasets
  inputs/                   # Reference weather and preserved pack parameters
  runs/scenario02_ef1b5703b8f6/
  requirements.txt
  README.md and historical preparation report
```

The eight former Python files have been consolidated into `bess_pipeline.py`.
Its labeled sections retain the former implementations. The original workspace
outside this folder is unchanged. Economic assessment remains excluded;
cycling degradation remains a secondary result.

## Running

Use the existing Python environment, or install `requirements.txt` on the
other machine. Restart the notebook kernel after this file consolidation,
then run cells 1 through 7. Cell 1 contains the editable parameters.

Cell 4 keeps the requested resume rule: if a model's Excel result already exists
in `runs/scenario02_ef1b5703b8f6/30days_results/`, load it and skip that model's
PMP solve. Missing model files are solved using the unchanged original solver.
Checkpoint signatures and SUCCESS labels are not required for skipping;
original convergence labels are retained. Unreadable existing files stop the
cell rather than causing an automatic solve over that file.

The former command-line runner is also included in the support file:

```powershell
python bess_pipeline.py --prepare-only
python bess_pipeline.py --run
python bess_pipeline.py --audit
```

`--prepare-only` executes the first three notebook cells. `--run` executes the
whole notebook with the same Excel-based resume rule. `--audit` performs the
former standalone original-file audit. These replace the old runner/audit
script names.

## Preserved model and parameters

The notebook's PMP declaration cell (2) and solver cell (4) are unchanged.
Electrical parameters, BVP settings, penalty updates, stop conditions and
power/energy equations are preserved.

Thermal parameters remain G=0.05 kg/s, Cp=4.180 kJ/(kg K), Ts=25 C,
Ton=32 C, Toff=29 C and COP=2. Pack parameters remain C=600 kJ/K,
r=2 K/kW, r_bat=0.013 ohm and V_nom=400 V.

Cooling decisions occur every 900 seconds. At or above 32 C cooling turns ON;
at or below 29 C it turns OFF; otherwise the previous state is held. The
unchanged analytical heat balance integrates heat/electricity over each
interval. Thermal/cooling coverage is 720 h, holding the last electrical and
ambient samples for the final half-hour. The electrical grid is unchanged:
1440 samples, 0..719.5 h, 1800-second spacing.

Weather uses distinct synthetic days with the original odd/even reference
profiles and hot durations constrained to their reference +/-1 hour.
Cycling uses the original rainflow/SEI equations, initial SOH=90% and the
original electrical/SOC nodes. Calendar aging is omitted; inherited Xu LMO
coefficients remain unvalidated for LFP.

## Assessment and plots

All former numeric tables, plotting data and styles remain unchanged by
consolidation. Rest requires abs(Pb(t))<=1 kW and
abs(Pb(t)*Pb(t-1))<0.5 kW^2, counted once per current sample.

The selected detail day is rank 2 by each day's largest high-ambient absolute
power peak across the four models (earlier day breaks ties). It appears in
subplot 5 of the dispatch figure with the fixed 17..18 h inset.

The dispatch figure is 3.5 x 8.2 inches; the three-panel daily figure is
3.5 x 5.8 inches. Temperature, damage, capacity loss and SOH are separate
figures. Cooling heat/electricity totals are separate; daily/cumulative
cooling electricity share a two-panel figure. All drawing support now lives
in the plot-style/report sections of `bess_pipeline.py`.

## Outputs and provenance

Results remain under the same fixed run folder; consolidation does not move,
relabel or overwrite existing results. Simulation output is in
`30days_results/`, assessment in `30days_results/assessment/`, and cooling
reports in its `cooling_energy/` subfolder.

`configuration.json` records the original imported run and is retained.
`project_metadata.json` consolidates the six former JSON documents into named
sections: `environment_snapshot`, `original_integrity_check`,
`original_integrity_manifest`, `project_origin`, `scenario_file_manifest` and
`baseline_thermal_parameters`. Their parameter/provenance values are retained.
The copied-file entries still check the remaining input files; the old cycling
module's entry records its earlier consolidation instead of requiring that file.
Original-workspace changes are reported without blocking; altered/missing
scenario input copies still block the final check.

`--audit` atomically updates only the `original_integrity_check` section,
preserving every other section. JSON configuration/checkpoint/report files
inside `runs/` remain separate and are not moved or converted.

`PREPARATION_REPORT.md` is historical. The `scenario_file_manifest` section
records current files, excluding `project_metadata.json` itself to avoid a
recursive checksum. `merged_json_sources` retains the old JSON file hashes.
No test scripts are needed to run the notebook.
