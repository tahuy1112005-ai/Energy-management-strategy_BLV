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

from copy import deepcopy
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd


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
