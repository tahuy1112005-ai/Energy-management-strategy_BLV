"""Self-contained support for the isolated 30-day BESS scenario.

Notebook parameters, PMP declarations and solver loops remain in the notebook.
Sections below retain the original weather, thermal, cycling, reporting and audit
implementations. CLI: --prepare-only, --run, or --audit.
"""

import argparse
import hashlib
import json
import os
import platform
import sys
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Preserve the original command-line runner's headless backend setup.
if __name__ == '__main__':
    os.environ.setdefault('MPLBACKEND', 'Agg')

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parent
SCENARIO_ROOT = ROOT


def _metadata_section(name):
    """Read one unchanged document from the consolidated project metadata."""
    metadata = json.loads((ROOT/'project_metadata.json').read_text(encoding='utf-8'))
    return metadata[name]


def _update_metadata_section(name, value):
    """Replace one section atomically while preserving all other metadata."""
    path = ROOT/'project_metadata.json'
    metadata = json.loads(path.read_text(encoding='utf-8'))
    metadata[name] = value
    temporary = path.with_suffix('.pending')
    try:
        temporary.write_text(json.dumps(metadata, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


# ========================================================================
# verify_original_files.py (consolidated; implementation retained)
# ========================================================================

"""Read-only SHA-256 audit of the original 30-day workspace.

All optional audit output is restricted to this new scenario folder.
Run: python bess_pipeline.py --audit
"""





def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit_original_files(*, output_path=None):
    manifest = _metadata_section('original_integrity_manifest')
    original_root = Path(manifest['original_root']).resolve()
    changed = []
    missing = []
    for relative, expected in manifest['original_files'].items():
        source = (original_root / relative).resolve()
        if not source.is_relative_to(original_root):
            raise ValueError(f'Original manifest contains a path outside its root: {relative}')
        if not source.is_file():
            missing.append(relative)
        elif source.stat().st_size != expected['bytes'] or sha256_file(source) != expected['sha256']:
            changed.append(relative)
    report = {
        'checked_utc': datetime.now(timezone.utc).isoformat(),
        'original_root': str(original_root),
        'checked_files': len(manifest['original_files']),
        'original_files_unchanged': not changed and not missing,
        'changed_files': changed,
        'missing_files': missing,
        'scope': manifest['scope'],
    }
    if output_path is not None:
        target = Path(output_path).resolve()
        if not target.is_relative_to(SCENARIO_ROOT):
            raise ValueError('Audit output must stay inside the scenario folder.')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target == (ROOT/'project_metadata.json').resolve():
            _update_metadata_section('original_integrity_check', report)
        else:
            target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


# ========================================================================
# scenario_plot_style.py (consolidated; implementation retained)
# ========================================================================

"""Shared print styling; no simulation or assessment calculations."""




IEEE_COLUMN_WIDTH_IN = 3.5
IEEE_HEIGHT_SCALE = 1.30
IEEE_DPI = 600
IEEE_RC = {
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 7.5,
    'mathtext.fontset': 'stix',
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'axes.titlesize': 7.5,
    'axes.titleweight': 'bold',
    'axes.titlepad': 3,
    'axes.labelsize': 7.5,
    'axes.labelpad': 2,
    'axes.linewidth': .55,
    'xtick.labelsize': 6.5,
    'ytick.labelsize': 6.5,
    'xtick.major.size': 2.5,
    'ytick.major.size': 2.5,
    'xtick.major.width': .5,
    'ytick.major.width': .5,
    'xtick.major.pad': 2,
    'ytick.major.pad': 2,
    'legend.fontsize': 6.5,
    'legend.framealpha': .9,
    'legend.borderpad': .25,
    'legend.labelspacing': .2,
    'legend.handlelength': 1.5,
    'legend.handletextpad': .35,
    'legend.columnspacing': .7,
    'lines.linewidth': .7,
    'lines.markersize': 2.5,
    'savefig.bbox': None,
}


def column_size(height_inches):
    return IEEE_COLUMN_WIDTH_IN, height_inches * IEEE_HEIGHT_SCALE


def save_ieee_figure(figure, output_stem, *, dpi=IEEE_DPI, show=True):
    """Keep the physical canvas width in PDF/PNG; do not crop with bbox='tight'."""
    output_stem = Path(output_stem)
    figure.savefig(output_stem.with_suffix('.png'), dpi=dpi, bbox_inches=None)
    figure.savefig(output_stem.with_suffix('.pdf'), bbox_inches=None)
    if show:
        plt.show()
    plt.close(figure)


# ========================================================================
# scenario_weather.py (consolidated; implementation retained)
# ========================================================================

"""Deterministic synthetic daily weather, referenced to the original Tamb pair.

The original electrical model uses half-hour input samples. Durations above
32 C are evaluated by zero-order hold, exactly as the thermal forcing uses them.
Each odd/even day has its own corresponding reference-duration bound (+/- 1 h).
"""



def generate_weather(reference_pair, *, seed=20261108, days=30, sample_hours=.5,
                     threshold_c=32., duration_tolerance_hours=1.):
    reference = np.asarray(reference_pair, dtype=float)
    points = int(round(24/sample_hours))
    if (reference.shape != (2, points) or not np.isfinite(reference).all()
            or not np.isclose(points*sample_hours, 24.) or days < 2):
        raise ValueError('Expected two finite reference days on the original daily sampling grid.')
    limit = int(np.floor(duration_tolerance_hours/sample_hours+1e-12))
    if limit < 1:
        raise ValueError('At least one sample of hot-duration variation is needed.')
    rng = np.random.default_rng(seed)
    offsets = np.resize(np.arange(-limit, limit+1), days)
    rng.shuffle(offsets)
    hour = np.arange(points)*sample_hours
    reference_counts = (reference > threshold_c).sum(axis=1)
    profiles = []
    rows = []
    # Smooth, daytime-only offset changes hot duration without shifting entire nights.
    envelope = np.where((hour >= 4) & (hour <= 20), np.sin(np.pi*(hour-4)/16)**2, 0.)
    positive = envelope > 1e-10
    reference_jump = float(np.max(np.abs(np.diff(np.r_[reference[0], reference[1], reference[0, 0]]))))
    jump_limit = 1.5*reference_jump
    for day in range(days):
        which = day % 2
        original = reference[which]
        target_count = int(reference_counts[which]+offsets[day])
        if not 0 < target_count < int(positive.sum()):
            raise ValueError('Requested hot duration is incompatible with the reference daytime profile.')
        accepted = None
        for _ in range(200):
            shift = rng.uniform(-.22, .22)
            shifted = np.interp((hour-shift) % 24, np.r_[hour, 24.], np.r_[original, original[0]])
            amplitude = rng.uniform(.94, 1.06)
            noise = rng.normal(0., .065, points)
            smooth_noise = sum(np.roll(noise, k)*weight for k, weight in zip(
                (-2, -1, 0, 1, 2), (1, 2, 3, 2, 1)))/9
            base = original.min()+amplitude*(shifted-original.min())+smooth_noise+rng.uniform(-.10, .10)
            crossings = (threshold_c-base[positive])/envelope[positive]
            ordered = np.sort(crossings)
            adjustment = .5*(ordered[target_count-1]+ordered[target_count])
            candidate = base+adjustment*envelope
            preceding = profiles[-1][-1] if profiles else candidate[0]
            if (int((candidate > threshold_c).sum()) == target_count
                    and candidate.min() >= reference.min()-2.
                    and candidate.max() <= reference.max()+2.
                    and np.max(np.abs(np.diff(np.r_[preceding, candidate]))) <= jump_limit):
                accepted = candidate
                break
        if accepted is None:
            raise ValueError(f'Could not create a continuous bounded weather day {day+1}.')
        profiles.append(accepted)
        rows.append(dict(
            Day=day+1, Reference_day=which+1, Reference_hot_h=float(reference_counts[which]*sample_hours),
            Target_hot_h=target_count*sample_hours,
            Scenario_hot_h=float((accepted > threshold_c).sum()*sample_hours),
            Hot_duration_difference_h=float(offsets[day]*sample_hours),
            Tamb_min_degC=float(accepted.min()), Tamb_max_degC=float(accepted.max()),
            Tamb_mean_degC=float(accepted.mean())))
    values = np.concatenate(profiles)
    if len({tuple(day) for day in profiles}) != days:
        raise ValueError('Generated ambient profiles are not unique.')
    daily = pd.DataFrame(rows)
    if np.max(np.abs(daily.Scenario_hot_h-daily.Reference_hot_h)) > duration_tolerance_hours+1e-12:
        raise ValueError('A generated day exceeds the confirmed reference-duration tolerance.')
    if not ((daily.Hot_duration_difference_h > 0).any() and (daily.Hot_duration_difference_h < 0).any()):
        raise ValueError('Need both longer and shorter hot periods than reference.')
    output = pd.DataFrame(dict(time_hour=np.arange(len(values))*sample_hours,
                               Day=np.repeat(np.arange(1, days+1), points),
                               Hour_of_day=np.tile(hour, days), Tamb_degC=values))
    return output, daily


# ========================================================================
# scenario_thermal.py (consolidated; implementation retained)
# ========================================================================

"""The original lumped BESS heat balance with sampled hysteresis control.

Public parameters retain the original units: C [kJ/K], r [K/kW],
r_bat [ohm], V_nom [V]. Internally power is W, heat capacity is J/K,
and interval energies are integrated analytically, not start-power rectangles.
"""




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


# ========================================================================
# battery_cycling_degradation.py (consolidated; implementation retained)
# ========================================================================

"""Offline cycling-only degradation from synchronized time, SoC and temperature.

Xu et al., IEEE TSG 9(2), 1131-1140 (2018), DOI: 10.1109/TSG.2016.2578950.
Implements equations (22), (25), (32), and the fresh-cell SEI mapping (12).
Defaults are the paper's LMO example, NOT an LFP calibration. No current input,
calendar damage, ECM modification, or streaming/chunk-wise state is required.

Rainflow records are counted once, including residual half cycles. Temperature
is a time-weighted mean over each record's endpoint window. Nested windows may
overlap: they describe cycle conditions, not additive elapsed-time exposure.
Damage is added once per rainflow record, NEVER at every sample in its window.
Time histories book each contribution at its later endpoint, retrospectively.
This offline convention does not claim the cycle was identifiable in real time.
"""




PAPER_URL = "https://doi.org/10.1109/TSG.2016.2578950"


@dataclass(frozen=True)
class CyclingParameters:
    k_T: float = 0.0693
    T_ref: float = 298.15
    k_sigma: float = 1.04
    sigma_ref: float = 0.50
    k_delta1: float = 1.40e5
    k_delta2: float = -0.501
    k_delta3: float = -1.23e5
    alpha_sei: float = 0.0575
    beta_sei: float = 121.0

    def __post_init__(self):
        if not np.isfinite(list(asdict(self).values())).all():
            raise ValueError("All cycling parameters must be finite scalars")
        if self.T_ref <= 0 or not 0 <= self.sigma_ref <= 1:
            raise ValueError("T_ref must be kelvin > 0; sigma_ref must be in [0, 1]")
        if not 0 <= self.alpha_sei <= 1 or self.beta_sei <= 0:
            raise ValueError("Require alpha_sei in [0, 1] and beta_sei > 0")
        # Ensures a positive, increasing stress on the whole normalized DoD domain.
        if self.k_delta1 <= 0 or self.k_delta2 >= 0 or self.k_delta1 + self.k_delta3 <= 0:
            raise ValueError("Require k_delta1 > 0, k_delta2 < 0, k_delta1+k_delta3 > 0")


@dataclass
class CyclingResult:
    cycles: pd.DataFrame
    history: pd.DataFrame
    metadata: dict = field(default_factory=dict)

    @property
    def summary(self):
        final = self.history.iloc[-1]
        summary = {
            "rainflow_records": len(self.cycles),
            "full_cycle_records": int((self.cycles["n_i"] == 1.0).sum()),
            "half_cycle_records": int((self.cycles["n_i"] == 0.5).sum()),
            "weighted_cycle_count": float(self.cycles["n_i"].sum()),
            "rainflow_EFC": float((self.cycles["n_i"] * self.cycles["DoD_i"]).sum()),
            "f_cyc": float(final["cumulative_damage"]),
            "capacity_loss_pct": float(final["capacity_loss_pct"]),
            "soh_pct": float(final["soh_pct"]),
        }
        if "initial_soh_pct" in self.metadata:
            summary.update({
                "initial_soh_pct": self.metadata["initial_soh_pct"],
                "initial_linearized_damage": self.metadata["initial_linearized_damage"],
                "total_linearized_damage": float(final["total_linearized_damage"]),
                "incremental_capacity_loss_pct": float(final["incremental_capacity_loss_pct"]),
            })
        return summary


def _array(values, name):
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a numeric one-dimensional array") from error
    if array.ndim != 1 or not np.isfinite(array).all():
        raise ValueError(f"{name} must be one-dimensional with finite values")
    return array


def _reversal_indices(values):
    """Endpoints plus local extrema; keep the last node of an interior plateau."""
    yield 0
    direction = 0
    for index in range(1, len(values)):
        change = np.sign(values[index] - values[index - 1])
        if change == 0:
            continue
        if direction and change != direction:
            yield index - 1
        direction = change
    yield len(values) - 1


def rainflow_cycles(soc):
    """Yield (range, mean, count, start_index, end_index), without binning.

    Stack rainflow counting with boundary/residual ranges weighted by 0.5.
    Range equals DoD; amplitude equals range/2. Output order is NOT chronological.
    Flat profiles yield no cycles. Plateaus retain original sample indices.
    """
    values = _array(soc, "soc")
    if len(values) < 2:
        return
    stack = []

    def record(left, right, count):
        return (float(abs(values[right] - values[left])),
                float((values[right] + values[left]) / 2), count, left, right)

    for index in _reversal_indices(values):
        stack.append(index)
        while len(stack) >= 3:
            older_range = abs(values[stack[-2]] - values[stack[-3]])
            newer_range = abs(values[stack[-1]] - values[stack[-2]])
            if newer_range < older_range:
                break
            if len(stack) == 3:
                if older_range > 0:
                    yield record(stack[0], stack[1], 0.5)
                del stack[0]
            else:
                if older_range > 0:
                    yield record(stack[-3], stack[-2], 1.0)
                del stack[-3:-1]
    for left, right in zip(stack[:-1], stack[1:]):
        if values[left] != values[right]:
            yield record(left, right, 0.5)


def stress_factors(dod, soc_mean, temperature_kelvin, parameters=None):
    """Return S_delta, S_sigma, S_T; zero DoD is explicitly zero cycling stress."""
    p = parameters if parameters is not None else CyclingParameters()
    delta, sigma, temperature = np.broadcast_arrays(
        np.asarray(dod, dtype=float), np.asarray(soc_mean, dtype=float),
        np.asarray(temperature_kelvin, dtype=float),
    )
    if not all(np.isfinite(a).all() for a in (delta, sigma, temperature)):
        raise ValueError("Cycle conditions must be finite")
    if np.any((delta < 0) | (delta > 1)) or np.any((sigma < 0) | (sigma > 1)):
        raise ValueError("DoD and mean SoC must be normalized to [0, 1]")
    if np.any(temperature <= 0):
        raise ValueError("Cycle temperature must be kelvin > 0")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            s_delta = np.zeros(delta.shape)
            positive = delta > 0
            denominator = p.k_delta1 * delta[positive]**p.k_delta2 + p.k_delta3
            if np.any(denominator <= 0):
                raise ValueError("DoD stress denominator is nonpositive")
            s_delta[positive] = 1.0 / denominator
            s_sigma = np.exp(p.k_sigma * (sigma - p.sigma_ref))
            s_temperature = np.exp(p.k_T * (temperature - p.T_ref) * p.T_ref / temperature)
    except FloatingPointError as error:
        raise ValueError("Stress calculation overflowed; check parameters and units") from error
    return s_delta, s_sigma, s_temperature


def capacity_loss(linearized_damage, parameters=None):
    """Equation (12), fresh-cell cycling-only loss fraction, numerically stable."""
    p = parameters if parameters is not None else CyclingParameters()
    damage = np.asarray(linearized_damage, dtype=float)
    if not np.isfinite(damage).all() or np.any(damage < 0):
        raise ValueError("Linearized damage must be finite and nonnegative")
    # expm1 preserves precision near zero; asymptotically the loss tends to one.
    with np.errstate(over="ignore", under="ignore"):
        return (-p.alpha_sei * np.expm1(-p.beta_sei * damage)
                - (1.0 - p.alpha_sei) * np.expm1(-damage))


def linearized_damage_from_soh(initial_soh_pct, parameters=None):
    """Invert the SEI retention mapping to find the equivalent historical damage.

    Requires 0 < SOH <= 100. The historical mechanisms are not identified by
    this inversion; it only initializes the selected nonlinear model.
    """
    p = parameters if parameters is not None else CyclingParameters()
    soh = float(initial_soh_pct)
    if not np.isfinite(soh) or not 0 < soh <= 100:
        raise ValueError("initial_soh_pct must be finite and in (0, 100]")
    if soh == 100:
        return 0.0
    target_retention = soh / 100.0
    lower = 0.0
    upper = -np.log(target_retention) / min(1.0, p.beta_sei)
    if not np.isfinite(upper):
        raise ValueError("SEI parameters give an unrepresentable initial damage")
    for _ in range(100):
        middle = (lower + upper) / 2.0
        retention = (p.alpha_sei * np.exp(-p.beta_sei * middle)
                     + (1.0 - p.alpha_sei) * np.exp(-middle))
        if retention > target_retention:
            lower = middle
        else:
            upper = middle
    return float((lower + upper) / 2.0)


def with_initial_soh(result, initial_soh_pct=95.0):
    """Return an independent result initialized at a specified SOH.

    Reuses the same SoC, temperature, rainflow cycles and cycling damage. Only
    the SEI baseline changes: f_total = f_initial + f_cyc. No capacity feedback
    into the ECM or thermal model is implied. Input result is never modified.

    capacity_loss_pct includes the historical loss; incremental_capacity_loss_pct
    excludes it and is measured against original nominal capacity (percentage
    points), not divided by the initial remaining capacity.
    """
    p = CyclingParameters(**result.metadata["parameters"])
    f_initial = linearized_damage_from_soh(initial_soh_pct, p)
    soh_initial = float(initial_soh_pct)
    loss_initial_pct = 100.0 - soh_initial
    cycles = result.cycles.copy(deep=True)
    history = result.history.copy(deep=True)
    for table in (cycles, history):
        cycling_damage = table["cumulative_damage"].to_numpy(dtype=float)
        table["total_linearized_damage"] = f_initial + cycling_damage
        # L(f_initial+f_cyc)-L(f_initial), stable even for tiny increments.
        with np.errstate(over="ignore", under="ignore"):
            incremental_loss = (
                -p.alpha_sei * np.exp(-p.beta_sei*f_initial) * np.expm1(-p.beta_sei*cycling_damage)
                -(1.0-p.alpha_sei) * np.exp(-f_initial) * np.expm1(-cycling_damage)
            )
        table["incremental_capacity_loss_pct"] = 100.0 * incremental_loss
        table["capacity_loss_pct"] = loss_initial_pct + 100.0 * incremental_loss
        table["soh_pct"] = soh_initial - 100.0 * incremental_loss
    cycles["capacity_loss_increment_pct"] = np.diff(
        np.r_[0.0, cycles.incremental_capacity_loss_pct.to_numpy()]
    )
    metadata = deepcopy(result.metadata)
    metadata.update({
        "initial_condition": "Equivalent historical damage inferred from initial SOH",
        "initial_soh_pct": soh_initial,
        "initial_capacity_loss_pct": loss_initial_pct,
        "initial_linearized_damage": f_initial,
        "capacity_loss_convention": "Total loss includes history; incremental loss is relative to original nominal capacity",
        "input_profile_policy": "Same SoC and temperature; no capacity/thermal feedback into ECM",
    })
    return CyclingResult(cycles, history, metadata)


def estimate_days_to_soh(result, target_soh_pct=60.0, *, initial_soh_pct=None,
                         time_unit="hours"):
    """Cycling-only projection using a constant average linearized damage rate.

    Invert the SEI model at both SOHs, then divide the additional damage by
    f_cyc/profile_duration_days. Do NOT extrapolate percentage capacity loss
    linearly. Fractional profile repetitions use this averaged-rate convention.

    This does not re-run rainflow on a long repeated profile: cycle mix and
    temperature are assumed stationary, with no extra calendar aging, capacity
    feedback, temperature feedback or changing resistance as the cell ages.
    Chemistry calibration and extrapolation uncertainty remain with the caller.
    """
    units_per_day = {"seconds": 86400.0, "minutes": 1440.0, "hours": 24.0, "days": 1.0,
                     "second": 86400.0, "minute": 1440.0, "hour": 24.0, "day": 1.0}
    if time_unit not in units_per_day:
        raise ValueError("time_unit must be seconds, minutes, hours or days")
    initial = float(result.metadata.get("initial_soh_pct", 100.0)
                    if initial_soh_pct is None else initial_soh_pct)
    target = float(target_soh_pct)
    parameters = CyclingParameters(**result.metadata["parameters"])
    initial_damage = linearized_damage_from_soh(initial, parameters)
    target_damage = linearized_damage_from_soh(target, parameters)
    if target > initial:
        raise ValueError("target_soh_pct cannot exceed initial_soh_pct")
    profile_time = result.history["time"].to_numpy(dtype=float)
    duration_days = float((profile_time[-1]-profile_time[0]) / units_per_day[time_unit])
    profile_damage = float(result.history["cumulative_damage"].iloc[-1])
    if not np.isfinite(duration_days) or duration_days <= 0:
        raise ValueError("Profile duration must be finite and positive")
    if not np.isfinite(profile_damage) or profile_damage < 0:
        raise ValueError("Profile cycling damage must be finite and nonnegative")
    additional_damage = max(0.0, target_damage-initial_damage)
    damage_per_day = profile_damage / duration_days
    if additional_damage == 0:
        days = repetitions = 0.0
    elif profile_damage == 0:
        days = repetitions = float("inf")
    else:
        repetitions = additional_damage / profile_damage
        days = repetitions * duration_days
    return {
        "initial_soh_pct": initial,
        "target_soh_pct": target,
        "profile_duration_days": duration_days,
        "profile_cycling_damage": profile_damage,
        "cycling_damage_per_day": damage_per_day,
        "initial_linearized_damage": initial_damage,
        "target_linearized_damage": target_damage,
        "additional_linearized_damage_required": additional_damage,
        "equivalent_profile_repetitions": repetitions,
        "estimated_days_to_target": days,
    }


def assess_cycling_degradation(time, soc, temperature, parameters=None, *,
                               soc_unit="fraction", temperature_unit="celsius",
                               zero_dod_tolerance=0.0):
    """Assess one complete synchronized profile; accepts no current input.

    time: increasing numeric nodes, any consistent unit (retained in output).
    soc_unit: 'fraction' [0,1] or 'percent' [0,100], explicitly selected. Never
        rescale by the observed min/max, which would change the actual DoD.
    temperature_unit: 'celsius' or 'kelvin'. Missing data and invalid SoC are
        rejected rather than clipped or silently interpolated across gaps.
    zero_dod_tolerance: optionally omit small ranges, in normalized SoC units.

    Use the whole history once: independently counting chunks would flush and
    double count boundary half cycles. Results start from a fresh cell (f_d=0).
    Calendar aging is intentionally absent; this is not a physical separation
    of measured cycling and calendar loss. Endpoint-window averaging of T is
    a modeling convention; full nested-cycle paths are not uniquely recovered.
    """
    p = parameters if parameters is not None else CyclingParameters()
    time = _array(time, "time")
    soc = _array(soc, "soc")
    temperature = _array(temperature, "temperature")
    if len(time) < 2 or len(time) != len(soc) or len(time) != len(temperature):
        raise ValueError("time, soc and temperature must have equal lengths >= 2")
    if np.any(np.diff(time) <= 0):
        raise ValueError("time must be strictly increasing, without duplicate nodes")
    if soc_unit not in ("fraction", "percent"):
        raise ValueError("soc_unit must be 'fraction' or 'percent'")
    soc = soc / 100.0 if soc_unit == "percent" else soc.copy()
    if np.any((soc < 0) | (soc > 1)):
        raise ValueError("SoC is outside the selected unit's physical range")
    if temperature_unit not in ("celsius", "kelvin"):
        raise ValueError("temperature_unit must be 'celsius' or 'kelvin'")
    kelvin = temperature + 273.15 if temperature_unit == "celsius" else temperature.copy()
    if np.any(kelvin <= 0):
        raise ValueError("Temperature must exceed absolute zero")
    if not np.isfinite(zero_dod_tolerance) or not 0 <= zero_dod_tolerance < 1:
        raise ValueError("zero_dod_tolerance must be in [0, 1)")

    # Prefix trapezoidal integral gives time-weighted averages on irregular grids.
    thermal_integral = np.r_[0.0, np.cumsum(0.5 * (kelvin[:-1] + kelvin[1:]) * np.diff(time))]
    rows = []
    skipped = 0
    for rainflow_id, (dod, mean, count, start, end) in enumerate(rainflow_cycles(soc), 1):
        if dod <= zero_dod_tolerance:
            skipped += 1
            continue
        left, right = sorted((start, end))
        average_temperature = (thermal_integral[right] - thermal_integral[left]) / (time[right] - time[left])
        rows.append({
            "rainflow_id": rainflow_id, "start_index": left, "end_index": right,
            "start_time": time[left], "end_time": time[right],
            "event_index": right, "event_time": time[right],
            "rainflow_amplitude": dod / 2.0, "DoD_i": dod,
            "SoC_avg_i": mean, "T_avg_K": average_temperature,
            "T_avg_degC": average_temperature - 273.15, "n_i": count,
        })
    columns = ["rainflow_id", "start_index", "end_index", "start_time", "end_time",
               "event_index", "event_time", "rainflow_amplitude", "DoD_i",
               "SoC_avg_i", "T_avg_K", "T_avg_degC", "n_i"]
    cycles = pd.DataFrame(rows, columns=columns)
    cycles = cycles.sort_values(["event_index", "rainflow_id"], kind="stable").reset_index(drop=True)
    cycles.insert(0, "cycle_number", np.arange(1, len(cycles) + 1))
    s_delta, s_sigma, s_temperature = stress_factors(
        cycles.DoD_i.to_numpy(dtype=float), cycles.SoC_avg_i.to_numpy(dtype=float),
        cycles.T_avg_K.to_numpy(dtype=float), p,
    )
    cycles["S_delta"] = s_delta
    cycles["S_sigma"] = s_sigma
    cycles["S_T"] = s_temperature
    with np.errstate(over="ignore", invalid="ignore"):
        damage = cycles.n_i.to_numpy(dtype=float) * s_delta * s_sigma * s_temperature
    if not np.isfinite(damage).all():
        raise ValueError("Cycling damage overflowed; check inputs and parameters")
    cycles["damage_contribution"] = damage
    cycles["cumulative_damage"] = np.cumsum(damage)
    if not np.isfinite(cycles.cumulative_damage).all():
        raise ValueError("Cumulative cycling damage overflowed")
    cycles["capacity_loss_pct"] = 100.0 * capacity_loss(cycles.cumulative_damage, p)
    cycles["capacity_loss_increment_pct"] = np.diff(np.r_[0.0, cycles.capacity_loss_pct])
    cycles["soh_pct"] = 100.0 - cycles.capacity_loss_pct

    # Add each contribution ONCE at its later endpoint, even for nested windows
    # and multiple events sharing one node. Never spread it over its interval.
    event_damage = np.zeros(len(time))
    if len(cycles):
        np.add.at(event_damage, cycles.event_index.to_numpy(dtype=int), damage)
    cumulative = np.cumsum(event_damage)
    loss_pct = 100.0 * capacity_loss(cumulative, p)
    history = pd.DataFrame({
        "time": time, "SoC": soc, "temperature_K": kelvin,
        "temperature_degC": kelvin - 273.15, "event_damage": event_damage,
        "cumulative_damage": cumulative, "capacity_loss_pct": loss_pct,
        "soh_pct": 100.0 - loss_pct,
    })
    return CyclingResult(cycles, history, {
        "paper": PAPER_URL, "parameters": asdict(p), "parameter_calibration": "LMO example, Xu Table I",
        "calendar_aging_included": False, "initial_condition": "fresh cell; f_d = 0",
        "soc_input_unit": soc_unit, "temperature_input_unit": temperature_unit,
        "temperature_averaging": "time-weighted piecewise-linear mean between cycle endpoints",
        "damage_time_convention": "offline retrospective attribution to later cycle endpoint",
        "overlap_policy": "nested windows may overlap for temperature means; each rainflow damage is added once",
        "zero_dod_tolerance": zero_dod_tolerance, "skipped_small_cycles": skipped,
    })


def plot_cycling_degradation(result, *, axes=None, label=None, x_axis="time"):
    """Plot damage, capacity loss and SOH; reuse axes to compare several models."""
    import matplotlib.pyplot as plt

    if x_axis not in ("time", "cycle"):
        raise ValueError("x_axis must be 'time' or 'cycle'")
    if axes is None:
        figure, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    else:
        axes = np.asarray(axes).ravel()
        if len(axes) != 3:
            raise ValueError("Provide three axes")
        figure = axes[0].figure
    keys = ("cumulative_damage", "capacity_loss_pct", "soh_pct")
    labels = ("Linearized cycling damage", "Capacity loss [%]", "SOH [%]")
    if x_axis == "time":
        x = result.history.time.to_numpy()
        ys = [result.history[key].to_numpy() for key in keys]
    else:
        x = np.r_[0, result.cycles.cycle_number.to_numpy()]
        ys = [np.r_[initial, result.cycles[key].to_numpy()]
              for initial, key in zip((0.0, 0.0, 100.0), keys)]
    for axis, y, ylabel in zip(axes, ys, labels):
        axis.step(x, y, where="post", label=label)
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.3)
    for axis in axes[1:]:
        axis.ticklabel_format(axis="y", style="plain", useOffset=False)
    axes[-1].set_xlabel("Time [input units]" if x_axis == "time" else "Rainflow record number")
    if label is not None:
        axes[0].legend()
    figure.tight_layout()
    return figure, axes


# ========================================================================
# scenario_project.py (consolidated; implementation retained)
# ========================================================================

"""Portable paths, configuration isolation, weather input preparation and audits."""







def _json_write_once(path, value):
    text = json.dumps(value, sort_keys=True, indent=2) + '\n'
    if path.exists():
        if path.read_text(encoding='utf-8') != text:
            raise ValueError(f'Refusing to replace a different immutable run configuration: {path}')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


def initialize_run(thermal_config, weather_config, *, label='scenario02', run_name=None):
    preserved = _metadata_section('baseline_thermal_parameters')
    for name in ('C', 'r', 'r_bat', 'V_nom'):
        if getattr(thermal_config, name) != preserved[name]:
            raise ValueError(f'{name} must remain exactly {preserved[name]} in its original units.')
    source_files = [ROOT/'bess_pipeline.py']
    dataset = sorted((ROOT/'8.2022').glob('*.xls*'))
    hashes = {str(path.relative_to(ROOT)).replace('\\', '/'): sha256_file(path)
              for path in source_files+dataset}
    notebook = json.loads((ROOT/'30days_scenario_02.ipynb').read_text(encoding='utf-8'))
    code = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
    payload = dict(thermal=asdict(thermal_config), weather=weather_config,
                   source_and_dataset_sha256=hashes,
                   notebook_code_sha256=hashlib.sha256('\n'.join(code).encode('utf-8')).hexdigest(),
                   electrical_grid='original 1440 nodes, 0..719.5 h, dt=.5 h',
                   thermal_grid='2880 intervals, 0..720 h, dt=900 s; last electrical/weather sample held',
                   weather_interpolation='zero-order hold, same convention as original thermal forcing',
                   aging_grid='original electrical/SOC nodes only; no SOC invented at 720 h')
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
    if run_name is None:
        run_root = ROOT/'runs'/f'{label}_{digest[:12]}'
    else:
        # This notebook explicitly reuses a single named run across machines.
        if not run_name or Path(run_name).name != run_name or run_name in ('.', '..'):
            raise ValueError('run_name must be a single folder name.')
        run_root = (ROOT/'runs'/run_name).resolve()
        if not run_root.is_relative_to((ROOT/'runs').resolve()):
            raise ValueError('The run directory must remain inside the scenario runs folder.')
    run_root.mkdir(parents=True, exist_ok=True)
    configuration_path = run_root/'configuration.json'
    # Preserve the original configuration of imported results. A source/Python
    # change must not create another folder or replace this historical record.
    if run_name is None or not configuration_path.exists():
        _json_write_once(configuration_path, payload)
    for folder in ('inputs', '30days_results', 'validation'):
        (run_root/folder).mkdir(exist_ok=True)
    return run_root


def _weather_csv_matches(path, expected):
    """Accept equivalent CSV formatting, but reject changed data/schema/order.

    Old Windows exports can contain CR-CR-LF, which universal newline reading
    turns into blank lines. CSV parsing handles these without rewriting them.
    The tolerance covers rounding from the existing %.15g serialization only.
    """
    try:
        saved = pd.read_csv(path, encoding='utf-8-sig')
        if saved.columns.tolist() != expected.columns.tolist() or saved.shape != expected.shape:
            return False
        actual = saved.to_numpy(dtype=float)
        wanted = expected.to_numpy(dtype=float)
        return bool(np.isfinite(actual).all()
                    and np.allclose(actual, wanted, rtol=0., atol=1e-10))
    except (ValueError, TypeError, UnicodeError, pd.errors.ParserError):
        return False


def prepare_weather(run_root, weather_config):

    reference = pd.read_csv(ROOT/'inputs/reference_ambient_2days.csv').Tamb_degC.to_numpy().reshape(2, 48)
    profile, daily = generate_weather(reference, **weather_config)
    for name, frame in [('ambient_30days.csv', profile), ('ambient_daily_validation.csv', daily)]:
        path = Path(run_root)/'inputs'/name
        text = frame.to_csv(index=False, float_format='%.15g', lineterminator='\n')
        if path.exists() and not _weather_csv_matches(path, frame):
            raise ValueError(f'Refusing to overwrite weather inputs of an existing run: {path}')
        if not path.exists():
            path.write_text(text, encoding='utf-8', newline='\n')
    return profile, daily


def plot_weather(profile, daily, output_dir):
    import matplotlib.pyplot as plt

    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    with plt.rc_context(IEEE_RC):
        fig,axes=plt.subplots(2,1,figsize=column_size(3.5))
        axes[0].plot(profile.time_hour/24,profile.Tamb_degC,color='#71564b',linewidth=.65)
        axes[0].axhline(32.,color='red',linestyle=':',linewidth=.5,label='32 '+chr(176)+'C')
        axes[0].set(xlabel='Time [days]',ylabel='Ambient temp. ['+chr(176)+'C]',
                    title='30-Day Ambient Temperature Scenario',xlim=(0,30))
        axes[0].set_xticks(range(0,31,5))
        axes[0].legend()
        axes[1].plot(daily.Day,daily.Reference_hot_h,'--s',color='gray',markersize=2.5,linewidth=.7,label='Original reference')
        axes[1].plot(daily.Day,daily.Scenario_hot_h,'-o',color='#4f86bd',markersize=2.5,linewidth=.7,label='New scenario')
        axes[1].fill_between(daily.Day,daily.Reference_hot_h-1,daily.Reference_hot_h+1,
                             color='gray',alpha=.13,label='Allowed duration +/-1 h')
        axes[1].set(xlabel='Day',ylabel='Time above 32 C [h]',xlim=(.5,30.5))
        axes[1].set_xticks([1,5,10,15,20,25,30])
        axes[1].set_xticks(range(1,31),minor=True)
        axes[1].legend(ncol=1,fontsize=6.5)
        for ax in axes:
            ax.grid(linewidth=.35,alpha=.2)
        fig.tight_layout(pad=.5,h_pad=.8)
        save_ieee_figure(fig,output_dir/'Ambient_scenario_30days')


def audit_project(run_root=None):
    manifest = _metadata_section('original_integrity_manifest')
    original_notebook = Path(manifest['original_root'])/'30days.ipynb'
    origin = _metadata_section('project_origin')
    if platform.node() == origin['origin_hostname'] and original_notebook.exists():
        original = audit_original_files()
    else:
        original = dict(original_files_unchanged=None,
                        note='Different machine or original workspace unavailable; the preparation audit is supplied and copied references are checked locally.')
    changed_copies = [item['copy'] for item in manifest['copied_files']
                      if not (ROOT/item['copy']).exists()
                      or sha256_file(ROOT/item['copy']) != item['sha256']]
    result = dict(original_audit=original, copied_reference_files_unchanged=not changed_copies,
                   changed_reference_copies=changed_copies)
    if run_root is not None:
        target = Path(run_root).resolve()/'validation'/'integrity_audit.json'
        if not target.is_relative_to(ROOT):
            raise ValueError('Audit output must stay within the scenario project.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


# ========================================================================
# scenario_outputs.py (consolidated; implementation retained)
# ========================================================================

"""Plots and cooling accounting from the scenario's validated thermal output."""




MODELS = ('I', 'II', 'III', 'IV')
STYLES = {
    'I': dict(color='#6b8e45', linestyle='-', marker='s'),
    'II': dict(color='#4f86bd', linestyle='--', marker='o'),
    'III': dict(color='#c4a42b', linestyle='-.', marker='^'),
    'IV': dict(color='#bf5f65', linestyle=':', marker='D'),
}


def export_cooling_report(assessment_file, *, dpi=IEEE_DPI, show=True):
    """No PMP or thermal recomputation: use the exact interval energies already saved."""
    assessment_file = Path(assessment_file)
    out = assessment_file.parent/'cooling_energy'
    out.mkdir(parents=True, exist_ok=True)
    with pd.ExcelFile(assessment_file) as book:
        summary = pd.read_excel(book, sheet_name='Thermal_summary', index_col=0)
        validation = pd.read_excel(book, sheet_name='Thermal_validation', index_col=0)
        assumptions = pd.read_excel(book, sheet_name='Assumptions', keep_default_na=False)
        nodes = {m: pd.read_excel(book, sheet_name=f'Thermal_nodes_{m}') for m in MODELS}
        intervals = {m: pd.read_excel(book, sheet_name=f'Thermal_intervals_{m}') for m in MODELS}
        daily = {m: pd.read_excel(book, sheet_name=f'Thermal_daily_{m}') for m in MODELS}
    settings = dict(zip(assumptions.Parameter, assumptions.Value))
    cop = float(settings['COP'])
    base = float(summary.iloc[0].Cooling_electric_kWh)
    summary['Electric_saving_vs_I_kWh'] = base-summary.Cooling_electric_kWh
    summary['Electric_reduction_vs_I_pct'] = 100*(1-summary.Cooling_electric_kWh/base) if base > 0 else np.nan
    daily_all = pd.concat([daily[m].assign(Model=f'Model {m}') for m in MODELS], ignore_index=True)
    with pd.ExcelWriter(out/'Cooling_energy_30days.xlsx', engine='openpyxl') as writer:
        summary.to_excel(writer, sheet_name='Comparison')
        daily_all.to_excel(writer, sheet_name='Daily_energy', index=False)
        validation.to_excel(writer, sheet_name='Validation')
        assumptions.to_excel(writer, sheet_name='Assumptions', index=False)
        for m in MODELS:
            nodes[m].to_excel(writer, sheet_name=f'Nodes_{m}', index=False)
            intervals[m].to_excel(writer, sheet_name=f'Intervals_{m}', index=False)
    def save(fig, stem):
        fig.tight_layout(pad=.5, h_pad=.8)
        save_ieee_figure(fig, out/stem, dpi=dpi, show=show)
    with plt.rc_context(IEEE_RC):
        # Battery temperature is exported independently by notebook cell 5.
        fig, axes = plt.subplots(3, 1, figsize=column_size(4.5), sharex=True)
        status = np.array([intervals[m].Cooling_on.to_numpy(dtype=int) for m in MODELS])
        axes[0].imshow(status, cmap=ListedColormap(['#eeeeee', '#4f86bd']), vmin=0, vmax=1,
                       aspect='auto', interpolation='nearest', extent=(0, 30, 4, 0))
        axes[0].set(yticks=[.5,1.5,2.5,3.5], yticklabels=[f'Model {m}' for m in MODELS],
                    title='Cooling Command: Blue = ON, Gray = OFF')
        for m in MODELS:
            style = STYLES[m]
            for ax, column in [(axes[1], 'Q_cool_mean_W'), (axes[2], 'P_cool_elec_mean_W')]:
                values = intervals[m][column].to_numpy()/1000
                ax.step(np.r_[intervals[m].Start_hour, 720.]/24, np.r_[values, values[-1]],
                        where='post', color=style['color'], linestyle=style['linestyle'],
                        linewidth=.65, label=f'Model {m}')
        axes[1].set(title='Cooling Thermal Power\n(15-minute Interval Mean)', ylabel='Thermal power [kW]')
        axes[2].set(title=f'Cooling Electrical Power (COP = {cop:g})',
                    ylabel='Electrical power [kW]', xlabel='Time [days]')
        for ax in axes[1:]:
            ax.legend(ncol=2, loc='best')
            ax.grid(linewidth=.35, alpha=.2)
        for ax in axes:
            ax.set_xlim(0,30)
            ax.set_xticks(range(0,31,5))
            ax.tick_params(direction='in', top=True, right=True)
        save(fig, 'Thermal_control_30days')

        # Separate total thermal extraction and total cooling electricity figures.
        for column, title, ylabel, stem in [
            ('Cooling_thermal_kWh', r'Total Cooling Heat Extraction ($Q_{cooling}$)', 'Thermal energy [kWh]', 'Cooling_heat_total_30days'),
            ('Cooling_electric_kWh', r'Total Cooling Electricity ($E_{cooling}$)', 'Electricity [kWh]', 'Cooling_electricity_total_30days')]:
            fig, ax = plt.subplots(figsize=column_size(1.0 if column == 'Cooling_electric_kWh' else 2.0))
            bars = ax.bar(summary.index, summary[column], color=[STYLES[m]['color'] for m in MODELS], alpha=.8)
            ax.bar_label(bars, fmt='%.2f', padding=2, fontsize=6.5)
            ax.set(title=title, ylabel=ylabel, ylim=(0,max(1e-6,float(summary[column].max())*1.2)))
            ax.grid(axis='y', linewidth=.35, alpha=.2)
            ax.set_axisbelow(True)
            save(fig, stem)

        # Daily and cumulative electricity form a separate two-panel figure.
        fig, axes = plt.subplots(2, 1, figsize=column_size(2.95))
        for m in MODELS:
            axes[0].plot(daily[m].Day, daily[m].Cooling_electric_kWh, **STYLES[m],
                         markerfacecolor='white', markersize=2.5, linewidth=.7, label=f'Model {m}')
            axes[1].plot(nodes[m].time_hour/24, nodes[m].Cooling_electric_cumulative_kWh,
                         color=STYLES[m]['color'], linestyle=STYLES[m]['linestyle'], linewidth=.7, label=f'Model {m}')
        axes[0].set(title='Daily Cooling Electricity', xlabel='Day', ylabel='Electricity [kWh/day]', xlim=(.5,30.5))
        axes[0].set_xticks([1,5,10,15,20,25,30])
        axes[0].set_xticks(range(1,31), minor=True)
        axes[1].set(title='Cumulative Cooling Electricity', xlabel='Time [days]', ylabel='Electricity [kWh]', xlim=(0,30))
        axes[1].set_xticks(range(0,31,5))
        for ax in axes:
            ax.legend(ncol=2)
            ax.grid(linewidth=.35, alpha=.2)
        save(fig, 'Cooling_energy_trends_30days')

        fig, axes = plt.subplots(2,1,figsize=column_size(3.5),sharex=True)
        for m in MODELS:
            axes[0].plot(daily[m].Day, daily[m].Cooling_ON_h, **STYLES[m],
                         markerfacecolor='white', markersize=2.5, linewidth=.7, label=f'Model {m}')
            axes[1].plot(daily[m].Day, daily[m].Cooling_activation_cycles, **STYLES[m],
                         markerfacecolor='white', markersize=2.5, linewidth=.7, label=f'Model {m}')
        axes[0].set(title='Daily Cooling Operating Duration', ylabel='Cooling ON [h/day]')
        axes[1].set(title='Daily Cooling Activations', ylabel='OFF-to-ON transitions', xlabel='Day')
        axes[1].yaxis.set_major_locator(MaxNLocator(integer=True))
        for ax in axes:
            ax.set_xlim(.5,30.5)
            ax.set_xticks([1,5,10,15,20,25,30])
            ax.set_xticks(range(1,31),minor=True)
            ax.legend(ncol=2)
            ax.grid(linewidth=.35,alpha=.2)
        save(fig,'Cooling_daily_operation_30days')

        fig,ax=plt.subplots(figsize=column_size(2.35))
        x=np.arange(4)
        for offset,column,label in [(-.25,'T_min_degC','Minimum'),
                                    (0.,'T_mean_degC','Time-weighted mean'),
                                    (.25,'T_max_degC','Maximum')]:
            bars=ax.bar(x+offset,summary[column],width=.24,label=label)
            ax.bar_label(bars,fmt='%.1f',padding=2,fontsize=6.5)
        ax.set(xticks=x,xticklabels=summary.index,ylabel='Temperature ['+chr(176)+'C]',
               title='30-day Battery Temperature Statistics',ylim=(0,float(summary.T_max_degC.max())*1.45))
        ax.legend(ncol=2,fontsize=6.5,loc='upper left')
        ax.grid(axis='y',linewidth=.35,alpha=.2)
        ax.set_axisbelow(True)
        save(fig,'Battery_temperature_statistics_30days')
    report = dict(run_directory=str(assessment_file.parents[2].resolve()),
        source_assessment=str(assessment_file.resolve()),
        original_integrity_audit_file=str(assessment_file.parents[2]/'validation/integrity_audit.json'),
        parameters={key: settings[key] for key in (
        'G', 'Cp', 'Ts', 'Ton', 'Toff', 'COP', 'C', 'r', 'r_bat', 'V_nom', 'thermal_step_seconds')},
        model_results=summary.reset_index().to_dict(orient='records'),
        validation=validation.reset_index().to_dict(orient='records'),
        limitations=[
            'Synthetic weather is a controlled scenario, not measured meteorological data.',
            'PMP equations/solver loops and electrical time step remain as in the baseline.',
            'Cooling is offline; its electrical demand is not fed back into dispatch.',
            'Control decisions occur only every 15 minutes; threshold crossings between decisions do not switch the command.',
            'Thermal/cooling coverage is 720 hours; electrical/SOC/aging coverage is 0..719.5 hours.',
            'The final half-hour holds the last electrical power and ambient sample.',
            'G*Cp*(T-Ts) retains the original ideal heat-exchange assumption; COP=2 is user-specified and no auxiliary loads are added.',
            'Cycling model retains Xu LMO example coefficients; this is not an LFP calibration.'])
    (out/'Final_report.json').write_text(json.dumps(report, indent=2, default=float)+'\n', encoding='utf-8')
    lines = ['# Scenario 02 simulation report', '',
             '## Parameters', '', '```', json.dumps(report['parameters'], indent=2), '```', '',
             '## Cooling and temperature comparison', '', '```', summary.to_string(), '```', '',
             '## Validation', '', '```', validation.to_string(), '```', '',
             '## Assumptions and limitations', '']
    lines.extend('- '+value for value in report['limitations'])
    lines.extend(['', 'Source integrity audit: `'+report['original_integrity_audit_file']+'`', ''])
    (out/'Final_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return summary, daily_all, validation


# ========================================================================
# run_scenario.py (consolidated; implementation retained)
# ========================================================================

"""Portable notebook runner. --prepare-only never executes the PMP solver cell."""





def cell_sources():
    notebook = json.loads((ROOT/'30days_scenario_02.ipynb').read_text(encoding='utf-8'))
    return [''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only', action='store_true', help='Prepare/validate inputs and paths; no PMP or thermal simulation.')
    mode.add_argument('--run', action='store_true', help='Execute the complete notebook, including all four original PMP solvers.')
    args = parser.parse_args()
    os.environ.setdefault('MPLBACKEND', 'Agg')
    os.chdir(ROOT)
    import matplotlib.pyplot as plt
    if plt.get_backend().lower() == 'agg':
        plt.show = lambda: None
    namespace = {'__name__': '__scenario_runner__', '__builtins__': __builtins__}
    sources = cell_sources()
    count = 3 if args.prepare_only else len(sources)
    for index, source in enumerate(sources[:count], 1):
        print(f'Executing cell {index}/{count}', flush=True)
        exec(compile(source, str(ROOT/f'notebook_cell_{index}.py'), 'exec'), namespace)
    if args.prepare_only:
        audit = audit_project(namespace['RUN_ROOT'])
        if audit['original_audit'].get('original_files_unchanged') is False:
            print('NOTICE: Original workspace changes recorded in integrity_audit.json; continuing with validated scenario copies.', flush=True)
        if not audit['copied_reference_files_unchanged']:
            raise RuntimeError('Copied scenario inputs/references failed integrity validation.')
        status = dict(status='PREPARED_NOT_SIMULATED', pmp_executed=False,
                      thermal_energy_results_available=False, run_directory=str(namespace['RUN_ROOT']),
                      weather_days=30, electrical_samples=namespace['N'],
                      electrical_dt_h=namespace['dt'], thermal_dt_seconds=namespace['THERMAL_CONFIG'].step_seconds,
                      thermal_duration_h=namespace['THERMAL_DURATION_HOURS'])
        (namespace['RUN_ROOT']/'preparation_status.json').write_text(json.dumps(status, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(status, indent=2), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--audit']:
        result = audit_original_files(output_path=SCENARIO_ROOT/'project_metadata.json')
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result['original_files_unchanged'] else 1)
    main()
