> Historical preparation record. Unused assessment/reference copies, the notebook builder and test files have since been removed at the user's request. See README.md and scenario_file_manifest.json for the current project. Original workspace files and existing scenario runs were preserved.

# Scenario 02 preparation report

Status: PREPARED_NOT_SIMULATED. No real PMP/production cooling run was performed.

## Confirmed implementation

- Thermal integration/control: analytical original heat balance, 15 minutes (900 s).
- Electrical model/time step: unchanged (30 minutes). Original PMP function and solver cells are byte-identical.
- Thermal/cooling horizon: 720 h; final electrical/Tamb sample held for 30 minutes.
- Electrical/SOC/cycling horizon: original 0..719.5 h; no invented terminal SOC.
- Weather: unique odd/even-reference days, each hot duration within original +/- 1 h.
- Hysteresis: ON at T>=32 C, OFF at T<=29 C, hold state between thresholds.
- Initial state OFF; first ambient is the initial battery temperature, as before.

## Final parameter configuration

```json
{
  "C": 600.0,
  "COP": 2.0,
  "Cp": 4.18,
  "G": 0.05,
  "Toff": 29.0,
  "Ton": 32.0,
  "Ts": 25.0,
  "V_nom": 400.0,
  "initial_cooling_on": false,
  "initial_temperature_c": null,
  "r": 2.0,
  "r_bat": 0.013,
  "step_seconds": 900.0
}
```

## Validation completed

- 16 scenario tests passed, including CSV newline/reuse and stale-kernel regressions plus a full notebook workflow with a controlled BVP stub.
- 36 inherited non-economic tests passed (52 current tests including 16 scenario tests).
- Original-copy PMP functions and solver source equality verified.
- Notebook schema validated; prepare-only command executed successfully on all 30 daily datasets.
- Unit/energy balance, hysteresis, OFF zeros, daily sums, 720 h/last-sample hold and resume verified.
- Portable integrity behavior checked for a different execution machine.
- 198 original non-cache files have unchanged SHA-256 hashes; no missing files.

## Cooling energy and daily energy statistics

Not calculated for the new dispatch: the user requested preparation only. After Run All,
the report includes total thermal/electrical kWh, daily min/max/mean/std, daily ON hours,
activation counts and min/max/time-weighted mean battery temperature for all four models.
No baseline or unit-test energy has been presented as a new-scenario result.

## New implementation files

- 30days_scenario_02.ipynb: central config and integration of the new scenario.
- scenario_thermal.py: exact 15-minute heat balance, hysteresis, energy/daily statistics.
- scenario_weather.py: deterministic reference-bounded 30-day weather.
- scenario_project.py: isolated run paths, weather input export, configuration identity, audits.
- scenario_outputs.py: cooling/temperature/status/energy plots and final reports.
- run_scenario.py: prepare-only or explicit full-run command.
- build_notebook.py: reproducible assembly from the preserved original notebook.
- test_scenario_02.py and verify_original_files.py: validation and source protection.
- requirements.txt/environment_snapshot.json: dependency versions (Python runtime not copied).

## Copied files (all byte-identical at preparation)

- `battery_cycling_degradation.py` <- `battery_cycling_degradation.py`
- `battery_assessment.py` <- `battery_assessment.py`
- `test_battery_cycling_degradation.py` <- `test_battery_cycling_degradation.py`
- `test_battery_assessment.py` <- `test_battery_assessment.py`
- `test_temperature_cooling.py` <- `test_temperature_cooling.py`
- `Battery_assessment_31_32.ipynb` <- `Battery_assessment_31_32.ipynb`
- `reference_original/30days.ipynb` <- `30days.ipynb`
- `8.2022/01.08.2022.xlsm` <- `8.2022/01.08.2022.xlsm`
- `8.2022/02.08.2022.xlsm` <- `8.2022/02.08.2022.xlsm`
- `8.2022/03.08.2022.xlsm` <- `8.2022/03.08.2022.xlsm`
- `8.2022/04.08.2022.xlsm` <- `8.2022/04.08.2022.xlsm`
- `8.2022/05.08.2022.xlsm` <- `8.2022/05.08.2022.xlsm`
- `8.2022/06.08.2022.xlsm` <- `8.2022/06.08.2022.xlsm`
- `8.2022/07.08.2022.xlsm` <- `8.2022/07.08.2022.xlsm`
- `8.2022/08.08.2022.xlsm` <- `8.2022/08.08.2022.xlsm`
- `8.2022/09.08.2022.xlsm` <- `8.2022/09.08.2022.xlsm`
- `8.2022/10.08.2022.xlsm` <- `8.2022/10.08.2022.xlsm`
- `8.2022/11.08.2022.xlsm` <- `8.2022/11.08.2022.xlsm`
- `8.2022/12.08.2022.xlsm` <- `8.2022/12.08.2022.xlsm`
- `8.2022/13.08.2022.xlsm` <- `8.2022/13.08.2022.xlsm`
- `8.2022/14.08.2022.xlsm` <- `8.2022/14.08.2022.xlsm`
- `8.2022/15.08.2022.xlsm` <- `8.2022/15.08.2022.xlsm`
- `8.2022/16.08.2022.xlsm` <- `8.2022/16.08.2022.xlsm`
- `8.2022/17.08.2022.xlsm` <- `8.2022/17.08.2022.xlsm`
- `8.2022/18.08.2022.xlsm` <- `8.2022/18.08.2022.xlsm`
- `8.2022/19.08.2022.xlsm` <- `8.2022/19.08.2022.xlsm`
- `8.2022/20.08.2022.xlsm` <- `8.2022/20.08.2022.xlsm`
- `8.2022/21.08.2022.xlsm` <- `8.2022/21.08.2022.xlsm`
- `8.2022/22.08.2022.xlsm` <- `8.2022/22.08.2022.xlsm`
- `8.2022/23.08.2022.xlsm` <- `8.2022/23.08.2022.xlsm`
- `8.2022/24.08.2022.xlsm` <- `8.2022/24.08.2022.xlsm`
- `8.2022/25.08.2022.xlsm` <- `8.2022/25.08.2022.xlsm`
- `8.2022/26.08.2022.xlsm` <- `8.2022/26.08.2022.xlsm`
- `8.2022/27.08.2022.xlsm` <- `8.2022/27.08.2022.xlsm`
- `8.2022/28.08.2022.xlsm` <- `8.2022/28.08.2022.xlsm`
- `8.2022/29.08.2022.xlsm` <- `8.2022/29.08.2022.xlsm`
- `8.2022/30.08.2022.xlsm` <- `8.2022/30.08.2022.xlsm`
- `8.2022/31.08.2022.xlsm` <- `8.2022/31.08.2022.xlsm`
- `reference_original/30days_results/Model_III_results_30days.xlsx` <- `30days_results/Model_III_results_30days.xlsx`
- `reference_original/30days_results/Model_II_checkpoint.json` <- `30days_results/Model_II_checkpoint.json`
- `reference_original/30days_results/Model_II_results_30days.xlsx` <- `30days_results/Model_II_results_30days.xlsx`
- `reference_original/30days_results/Model_IV_results_30days.xlsx` <- `30days_results/Model_IV_results_30days.xlsx`
- `reference_original/30days_results/Model_I_checkpoint.json` <- `30days_results/Model_I_checkpoint.json`
- `reference_original/30days_results/Model_I_results_30days.xlsx` <- `30days_results/Model_I_results_30days.xlsx`
- `reference_original/30days_results/Solver_report_30days.xlsx` <- `30days_results/Solver_report_30days.xlsx`
- `reference_original/30days_results/assessment/Assessment_30days.xlsx` <- `30days_results/assessment/Assessment_30days.xlsx`
- `reference_original/30days_results/assessment/Battery_degradation_30days.pdf` <- `30days_results/assessment/Battery_degradation_30days.pdf`
- `reference_original/30days_results/assessment/Battery_degradation_30days.png` <- `30days_results/assessment/Battery_degradation_30days.png`
- `reference_original/30days_results/assessment/Daily_abrupt_transitions_30days.pdf` <- `30days_results/assessment/Daily_abrupt_transitions_30days.pdf`
- `reference_original/30days_results/assessment/Daily_abrupt_transitions_30days.png` <- `30days_results/assessment/Daily_abrupt_transitions_30days.png`
- `reference_original/30days_results/assessment/Daily_resting_time_30days.pdf` <- `30days_results/assessment/Daily_resting_time_30days.pdf`
- `reference_original/30days_results/assessment/Daily_resting_time_30days.png` <- `30days_results/assessment/Daily_resting_time_30days.png`
- `reference_original/30days_results/assessment/Daily_shaving_30days.pdf` <- `30days_results/assessment/Daily_shaving_30days.pdf`
- `reference_original/30days_results/assessment/Daily_shaving_30days.png` <- `30days_results/assessment/Daily_shaving_30days.png`
- `reference_original/30days_results/assessment/Dispatch_profiles_30days.pdf` <- `30days_results/assessment/Dispatch_profiles_30days.pdf`
- `reference_original/30days_results/assessment/Dispatch_profiles_30days.png` <- `30days_results/assessment/Dispatch_profiles_30days.png`
- `reference_original/30days_results/assessment/Model_comparison_30days.pdf` <- `30days_results/assessment/Model_comparison_30days.pdf`
- `reference_original/30days_results/assessment/Model_comparison_30days.png` <- `30days_results/assessment/Model_comparison_30days.png`
- `reference_original/30days_results/assessment/cooling_energy/Cooling_energy_30days.xlsx` <- `30days_results/assessment/cooling_energy/Cooling_energy_30days.xlsx`
- `reference_original/30days_results/assessment/cooling_energy/Cooling_energy_comparison_30days.pdf` <- `30days_results/assessment/cooling_energy/Cooling_energy_comparison_30days.pdf`
- `reference_original/30days_results/assessment/cooling_energy/Cooling_energy_comparison_30days.png` <- `30days_results/assessment/cooling_energy/Cooling_energy_comparison_30days.png`
- `reference_original/30days_results/assessment/cooling_energy/Cooling_energy_trends_30days.pdf` <- `30days_results/assessment/cooling_energy/Cooling_energy_trends_30days.pdf`
- `reference_original/30days_results/assessment/cooling_energy/Cooling_energy_trends_30days.png` <- `30days_results/assessment/cooling_energy/Cooling_energy_trends_30days.png`

## Prepared run

`runs\scenario02_3901efcb6cd0`

Inputs and ambient preview are present. The new results directory is intentionally empty.

## Assumptions and limitations

- Weather is synthetic and bounded by the corresponding original profile, not measured weather.
- Ambient and battery power are held between original 30-minute electrical nodes.
- Cooling command changes only at 15-minute samples; between-sample crossings do not switch it.
- Cooling is offline; electric demand is not fed back to the unchanged PMP.
- The original ideal heat exchange G*Cp*(T-Ts) is retained; no separate auxiliaries/capacity limit.
- COP=2 is user-specified; no equipment performance calibration is implied.
- The original Xu LMO cycling coefficients remain unvalidated for LFP; no calendar aging.
- Real new-weather PMP convergence has not been evaluated.

## Scope update

Economic assessment is excluded. The scenario copies of `battery_economic_assessment.py` and its test were removed; original files are unchanged.

Cycling degradation remains a secondary result, as confirmed by the user. Cooling operation is the primary assessment.

## Windows CSV / audit policy fix

Weather reuse now compares CSV schema and numeric data, allowing LF, CRLF and legacy CR-CR-LF files without overwriting them. Real data differences are still rejected. New exports use explicit LF newlines.

Two consecutive prepare-only runs succeeded with the same run ID and no PMP execution. The original workspace currently has 11 missing files in the unrelated optimized-pairs results; this is reported without blocking, as confirmed by the user. Scenario reference/input copy integrity remains enforced. The initial 198-file unchanged check above records preparation time, not the current state of that unrelated folder.

## Notebook weather-helper reload

Cell 3 explicitly reloads the local weather/project modules and rebinds prepare_weather before reading inputs, so a reused Jupyter kernel cannot keep the obsolete string-comparison guard. The complete cell was verified against run scenario02_3901efcb6cd0 with a deliberately stale alias; 1440 samples loaded and existing CSV bytes were unchanged.


## Source consolidation (2026-11-12)

The eight former Python scripts were consolidated into `bess_pipeline.py`.
Their old names in this document describe historical preparation only.
Notebook cells 2 (PMP declarations) and 4 (solver/resume) were retained byte
for byte. Parameter assignments and assessment/report calculations were
preserved; imports and the source-file inventory were adapted to one module.

Validation completed before removing old scripts:
- All 31 function/class ASTs match the original implementations after removing
  sibling imports and normalizing only the source-file inventory assignment.
- Exact before/after equality for generated weather and four models' thermal
  nodes, interval/daily cooling energy, rainflow, cycling damage, loss and SOH.
- All seven notebook cells executed in an isolated temporary copy with only
  `bess_pipeline.py`; four saved model files loaded and zero BVP calls.
- Existing monthly, daily, selected-day, ranking and cooling tables matched.
- All existing run-file hashes and all recorded original-workspace file states
  stayed unchanged. The temporary validation copy and obsolete scripts/caches
  were removed. No production output was regenerated during consolidation.

Run the notebook after restarting its kernel, or use
`python bess_pipeline.py --prepare-only`, `--run`, or `--audit`.


## JSON consolidation (2026-11-12)

Six configuration/provenance JSON documents were merged into
`project_metadata.json`; named sections retain the original document values.
The source-file inventory was refreshed and excludes the metadata file itself
from its own checksum list. `merged_json_sources` preserves the old hashes.
All original-project references and guarded thermal parameter units/values
were retained. The notebook file itself was not changed.

Validation used an isolated copy containing only the merged project JSON:
- Notebook cells 1-4 loaded 1440 weather samples and four existing model Excel
  files without a BVP call; all four frozen pack-parameter guards still reject
  changes. The final audit cell passed the copied-input checks.
- The CLI audit updates only its report section, preserving all other data.
- A controlled atomic-write failure preserved the complete metadata file and
  cleaned its pending file.
- All existing run files and recorded original-workspace file states remained
  byte-identical. Numerical/plot functions were not modified.

The six obsolete JSON files and temporary validation copy were removed.
JSON files in `runs/` remain separate and unchanged.
