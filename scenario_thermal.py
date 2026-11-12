"""The original lumped BESS heat balance with sampled hysteresis control.

Public parameters retain the original units: C [kJ/K], r [K/kW],
r_bat [ohm], V_nom [V]. Internally power is W, heat capacity is J/K,
and interval energies are integrated analytically, not start-power rectangles.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ThermalConfig:
    G: float
    Cp: float
    Ts: float
    Ton: float
    Toff: float
    COP: float
    C: float
    r: float
    r_bat: float
    V_nom: float
    step_seconds: float = 900.0
    initial_temperature_c: float | None = None
    initial_cooling_on: bool = False

    def __post_init__(self):
        values = [v for k, v in asdict(self).items()
                  if k not in ('initial_temperature_c', 'initial_cooling_on')]
        if not np.isfinite(values).all():
            raise ValueError('Thermal parameters must be finite.')
        if min(self.Cp, self.COP, self.C, self.r, self.V_nom, self.step_seconds) <= 0:
            raise ValueError('Cp, COP, C, r, V_nom and step_seconds must be positive.')
        if min(self.G, self.r_bat) < 0 or not self.Toff < self.Ton:
            raise ValueError('Require G/r_bat >= 0 and Toff < Ton.')
        if min(self.Ts, self.Toff) <= -273.15:
            raise ValueError('Temperatures must be above absolute zero.')
        if self.initial_temperature_c is not None and (
                not np.isfinite(self.initial_temperature_c) or self.initial_temperature_c <= -273.15):
            raise ValueError('Invalid initial battery temperature.')


@dataclass
class ThermalResult:
    nodes: pd.DataFrame
    intervals: pd.DataFrame
    daily: pd.DataFrame
    summary: dict
    validation: dict


def cooling_state(temperature_c, was_on, config):
    """At a control instant: >= Ton turns ON; <= Toff turns OFF; otherwise hold."""
    if temperature_c >= config.Ton:
        return True
    if temperature_c <= config.Toff:
        return False
    return bool(was_on)


def analytic_interval(temperature_c, battery_power_kw, ambient_c, on, seconds, config):
    """Solve C*dT/dt = I^2*R + (Tamb-T)/r + u*G*Cp*(Ts-T).

    Power, ambient temperature, and cooling command are held over this interval.
    Cooling heat varies with T; its integrated energy uses the exact integral of T.
    """
    if not np.isfinite([temperature_c, battery_power_kw, ambient_c, seconds]).all() or seconds <= 0:
        raise ValueError('Invalid interval inputs.')
    capacity_j_per_k = config.C * 1000.0
    resistance_k_per_w = config.r / 1000.0
    cp_j_per_kg_k = config.Cp * 1000.0
    coolant_w_per_k = config.G * cp_j_per_kg_k if on else 0.0
    current_a = battery_power_kw * 1000.0 / config.V_nom
    generated_w = current_a**2 * config.r_bat
    wall_w_per_k = 1.0 / resistance_k_per_w
    conductance = wall_w_per_k + coolant_w_per_k
    rate = conductance / capacity_j_per_k
    equilibrium_c = (generated_w + wall_w_per_k*ambient_c + coolant_w_per_k*config.Ts) / conductance
    response = -np.expm1(-rate*seconds)
    end_c = temperature_c + (equilibrium_c-temperature_c)*response
    integral_temperature_c_s = equilibrium_c*seconds + (temperature_c-equilibrium_c)*response/rate
    generated_j = generated_w*seconds
    wall_j = wall_w_per_k*(ambient_c*seconds-integral_temperature_c_s)
    cooling_j = coolant_w_per_k*(integral_temperature_c_s-config.Ts*seconds) if on else 0.0
    if cooling_j < -1e-5:
        raise ValueError('Coolant heats the battery in this interval; this cooling-only accounting needs review.')
    cooling_j = max(0.0, float(cooling_j))
    electricity_j = cooling_j/config.COP
    stored_j = capacity_j_per_k*(end_c-temperature_c)
    return dict(
        T_end_degC=float(end_c), T_integral_degC_s=float(integral_temperature_c_s),
        Q_gen_W=float(generated_w), Q_cool_start_W=float(coolant_w_per_k*(temperature_c-config.Ts)),
        Q_cool_mean_W=float(cooling_j/seconds), P_cool_elec_mean_W=float(electricity_j/seconds),
        Cooling_thermal_kWh=float(cooling_j/3_600_000.0),
        Cooling_electric_kWh=float(electricity_j/3_600_000.0),
        Generated_heat_kWh=float(generated_j/3_600_000.0),
        Ambient_heat_into_battery_kWh=float(wall_j/3_600_000.0),
        Thermal_balance_residual_kWh=float((stored_j-generated_j-wall_j+cooling_j)/3_600_000.0))


def simulate_thermal(time_hour, battery_power_kw, ambient_c, config, *, duration_hours=720.0):
    """Replay the unchanged dispatch, with zero-order hold and a final sample hold.

    Electrical nodes remain 0..719.5 h. Thermal nodes are 0..720 h at 15 min.
    The last half-hour is explicitly supplied by the last saved power/Tamb sample.
    No additional electrical/SOC solution is invented.
    """
    t = np.asarray(time_hour, dtype=float)
    power = np.asarray(battery_power_kw, dtype=float)
    ambient = np.asarray(ambient_c, dtype=float)
    if (t.ndim != 1 or len(t) < 2 or power.shape != t.shape or ambient.shape != t.shape
            or not np.isfinite(np.column_stack((t, power, ambient))).all()
            or not (np.diff(t) > 0).all() or not np.isclose(t[0], 0)):
        raise ValueError('Need finite synchronized arrays on an increasing time grid starting at zero.')
    if np.min(ambient) < config.Ts:
        raise ValueError('This scenario assumes Tamb >= coolant inlet temperature; review cold-ambient heating otherwise.')
    if not np.isfinite(duration_hours) or duration_hours <= 0 or t[-1] > duration_hours:
        raise ValueError('Invalid thermal horizon.')
    count = int(round(duration_hours*3600/config.step_seconds))
    if not np.isclose(count*config.step_seconds, duration_hours*3600):
        raise ValueError('The thermal step must divide the requested horizon.')
    thermal_t = np.arange(count+1)*config.step_seconds/3600
    # Original electrical samples are held, not interpolated or changed.
    source_index = np.searchsorted(t, thermal_t[:-1], side='right')-1
    source_index = np.clip(source_index, 0, len(t)-1)
    initial = float(ambient[0] if config.initial_temperature_c is None else config.initial_temperature_c)
    if initial < config.Ts:
        raise ValueError('Initial battery temperature below Ts requires a separate heating model.')
    temperatures = [initial]
    rows = []
    was_on = bool(config.initial_cooling_on)
    for k, index in enumerate(source_index):
        start_c = temperatures[-1]
        on = cooling_state(start_c, was_on, config)
        outcome = analytic_interval(start_c, power[index], ambient[index], on, config.step_seconds, config)
        rows.append(dict(
            Start_hour=float(thermal_t[k]), End_hour=float(thermal_t[k+1]),
            Day=int(np.floor(thermal_t[k]/24))+1, Source_sample=int(index),
            P_battery_kW=float(power[index]), Tamb_degC=float(ambient[index]),
            T_start_degC=start_c, Cooling_on=bool(on), Cooling_activation=int(on and not was_on),
            Interval_seconds=float(config.step_seconds), **outcome))
        temperatures.append(outcome['T_end_degC'])
        was_on = on
    intervals = pd.DataFrame(rows)
    nodes = pd.DataFrame(dict(
        time_hour=thermal_t, Time_day=thermal_t/24, T_battery_degC=temperatures,
        # At the terminal node the last command is reported; no new zero-duration activation is counted.
        Cooling_on=np.r_[intervals.Cooling_on.to_numpy(dtype=bool), intervals.Cooling_on.iloc[-1]],
        Cooling_thermal_cumulative_kWh=np.r_[0., intervals.Cooling_thermal_kWh.cumsum()],
        Cooling_electric_cumulative_kWh=np.r_[0., intervals.Cooling_electric_kWh.cumsum()]))
    daily_rows = []
    for day, group in intervals.groupby('Day', sort=True):
        seconds = float(group.Interval_seconds.sum())
        daily_rows.append(dict(
            Day=int(day), Observed_h=seconds/3600,
            Cooling_thermal_kWh=float(group.Cooling_thermal_kWh.sum()),
            Cooling_electric_kWh=float(group.Cooling_electric_kWh.sum()),
            Cooling_ON_h=float(group.loc[group.Cooling_on, 'Interval_seconds'].sum()/3600),
            Cooling_activation_cycles=int(group.Cooling_activation.sum()),
            T_min_degC=float(min(group.T_start_degC.min(), group.T_end_degC.min())),
            T_max_degC=float(max(group.T_start_degC.max(), group.T_end_degC.max())),
            T_mean_degC=float(group.T_integral_degC_s.sum()/seconds)))
    daily = pd.DataFrame(daily_rows)
    seconds = float(intervals.Interval_seconds.sum())
    summary = dict(
        Thermal_duration_h=seconds/3600, Thermal_step_seconds=config.step_seconds,
        Cooling_thermal_kWh=float(intervals.Cooling_thermal_kWh.sum()),
        Cooling_electric_kWh=float(intervals.Cooling_electric_kWh.sum()),
        Cooling_ON_h=float(intervals.loc[intervals.Cooling_on, 'Interval_seconds'].sum()/3600),
        Cooling_activation_cycles=int(intervals.Cooling_activation.sum()),
        T_min_degC=float(nodes.T_battery_degC.min()), T_max_degC=float(nodes.T_battery_degC.max()),
        T_mean_degC=float(intervals.T_integral_degC_s.sum()/seconds),
        Daily_electric_min_kWh=float(daily.Cooling_electric_kWh.min()),
        Daily_electric_max_kWh=float(daily.Cooling_electric_kWh.max()),
        Daily_electric_mean_kWh=float(daily.Cooling_electric_kWh.mean()),
        Daily_electric_std_kWh=float(daily.Cooling_electric_kWh.std(ddof=0)),
        Final_sample_hold_h=float(max(0., duration_hours-t[-1])), COP=config.COP)
    previous = np.r_[bool(config.initial_cooling_on), intervals.Cooling_on.to_numpy()[:-1]]
    expected = np.array([cooling_state(v, p, config) for v, p in zip(intervals.T_start_degC, previous)])
    off = ~intervals.Cooling_on.to_numpy(dtype=bool)
    validation = dict(
        Finite_outputs=bool(np.isfinite(intervals.select_dtypes(include=np.number).to_numpy()).all()),
        Hysteresis_violations=int(np.count_nonzero(expected != intervals.Cooling_on.to_numpy())),
        OFF_nonzero_cooling_count=int(np.count_nonzero(intervals.loc[off, 'Q_cool_mean_W'].to_numpy() != 0.)),
        OFF_nonzero_electric_count=int(np.count_nonzero(intervals.loc[off, 'P_cool_elec_mean_W'].to_numpy() != 0.)),
        Step_max_error_seconds=float(np.max(np.abs(np.diff(nodes.time_hour)*3600-config.step_seconds))),
        Max_thermal_balance_residual_kWh=float(intervals.Thermal_balance_residual_kWh.abs().max()),
        Electric_integral_error_kWh=float(abs(np.sum(intervals.P_cool_elec_mean_W*intervals.Interval_seconds/3_600_000)
                                                -summary['Cooling_electric_kWh'])),
        Daily_electric_sum_error_kWh=float(abs(daily.Cooling_electric_kWh.sum()-summary['Cooling_electric_kWh'])))
    if (not validation['Finite_outputs'] or validation['Hysteresis_violations']
            or validation['OFF_nonzero_cooling_count'] or validation['OFF_nonzero_electric_count']
            or validation['Max_thermal_balance_residual_kWh'] > 1e-8
            or validation['Electric_integral_error_kWh'] > 1e-8):
        raise ValueError(f'Thermal validation failed: {validation}')
    return ThermalResult(nodes, intervals, daily, summary, validation)
