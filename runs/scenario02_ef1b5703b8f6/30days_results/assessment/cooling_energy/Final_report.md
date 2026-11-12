# Scenario 02 simulation report

## Parameters

```
{
  "G": 0.05,
  "Cp": 4.18,
  "Ts": 25,
  "Ton": 32,
  "Toff": 29,
  "COP": 2,
  "C": 600,
  "r": 2,
  "r_bat": 0.013,
  "V_nom": 400,
  "thermal_step_seconds": 900
}
```

## Cooling and temperature comparison

```
           Thermal_duration_h  Thermal_step_seconds  Cooling_thermal_kWh  Cooling_electric_kWh  Cooling_ON_h  Cooling_activation_cycles  T_min_degC  T_max_degC  T_mean_degC  Daily_electric_min_kWh  Daily_electric_max_kWh  Daily_electric_mean_kWh  Daily_electric_std_kWh  Final_sample_hold_h  COP  Electric_saving_vs_I_kWh  Electric_reduction_vs_I_pct
Model                                                                                                                                                                                                                                                                                                                                                         
Model I                   720                   900           346.265085            173.132542        270.75                         47   27.360405   37.421439    30.107359                3.324559                9.113629                 5.771085                1.642540                  0.5    2                  0.000000                     0.000000
Model II                  720                   900           340.492246            170.246123        265.00                         48   27.358652   37.491507    30.109436                3.306689                9.059469                 5.674871                1.564498                  0.5    2                  2.886419                     1.667173
Model III                 720                   900           325.447809            162.723905        267.50                         47   27.377119   34.651638    29.972662                3.276248                8.449197                 5.424130                1.414881                  0.5    2                 10.408638                     6.011948
Model IV                  720                   900           322.360166            161.180083        264.50                         48   27.378201   34.665686    29.970771                3.007550                8.457594                 5.372669                1.415744                  0.5    2                 11.952460                     6.903647
```

## Validation

```
           Finite_outputs  Hysteresis_violations  OFF_nonzero_cooling_count  OFF_nonzero_electric_count  Step_max_error_seconds  Max_thermal_balance_residual_kWh  Electric_integral_error_kWh  Daily_electric_sum_error_kWh
Model                                                                                                                                                                                                                       
Model I              True                      0                          0                           0                       0                      1.875580e-15                            0                  0.000000e+00
Model II             True                      0                          0                           0                       0                      1.940255e-15                            0                  2.842171e-14
Model III            True                      0                          0                           0                       0                      2.004931e-15                            0                  2.842171e-14
Model IV             True                      0                          0                           0                       0                      1.681555e-15                            0                  2.842171e-14
```

## Assumptions and limitations

- Synthetic weather is a controlled scenario, not measured meteorological data.
- PMP equations/solver loops and electrical time step remain as in the baseline.
- Cooling is offline; its electrical demand is not fed back into dispatch.
- Control decisions occur only every 15 minutes; threshold crossings between decisions do not switch the command.
- Thermal/cooling coverage is 720 hours; electrical/SOC/aging coverage is 0..719.5 hours.
- The final half-hour holds the last electrical power and ambient sample.
- G*Cp*(T-Ts) retains the original ideal heat-exchange assumption; COP=2 is user-specified and no auxiliary loads are added.
- Cycling model retains Xu LMO example coefficients; this is not an LFP calibration.

Source integrity audit: `D:\VScode\30days_scenario_02\runs\scenario02_ef1b5703b8f6\validation\integrity_audit.json`
