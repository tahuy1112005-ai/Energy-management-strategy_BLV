"""Portable paths, configuration isolation, weather input preparation and audits."""

import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from verify_original_files import audit_original_files, sha256_file


ROOT = Path(__file__).resolve().parent


def _json_write_once(path, value):
    text = json.dumps(value, sort_keys=True, indent=2) + '\n'
    if path.exists():
        if path.read_text(encoding='utf-8') != text:
            raise ValueError(f'Refusing to replace a different immutable run configuration: {path}')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


def initialize_run(thermal_config, weather_config, *, label='scenario02', run_name=None):
    preserved = json.loads((ROOT/'inputs/baseline_thermal_parameters.json').read_text(encoding='utf-8'))
    for name in ('C', 'r', 'r_bat', 'V_nom'):
        if getattr(thermal_config, name) != preserved[name]:
            raise ValueError(f'{name} must remain exactly {preserved[name]} in its original units.')
    source_files = [ROOT/name for name in ('scenario_thermal.py', 'scenario_weather.py',
        'scenario_project.py', 'scenario_outputs.py', 'battery_cycling_degradation.py')]
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
    from scenario_weather import generate_weather

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
    from scenario_plot_style import IEEE_RC, column_size, save_ieee_figure

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
    manifest = json.loads((ROOT/'original_integrity_manifest.json').read_text(encoding='utf-8'))
    original_notebook = Path(manifest['original_root'])/'30days.ipynb'
    origin = json.loads((ROOT/'project_origin.json').read_text(encoding='utf-8'))
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
