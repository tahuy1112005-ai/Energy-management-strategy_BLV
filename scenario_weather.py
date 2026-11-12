"""Deterministic synthetic daily weather, referenced to the original Tamb pair.

The original electrical model uses half-hour input samples. Durations above
32 C are evaluated by zero-order hold, exactly as the thermal forcing uses them.
Each odd/even day has its own corresponding reference-duration bound (+/- 1 h).
"""

import numpy as np
import pandas as pd


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
