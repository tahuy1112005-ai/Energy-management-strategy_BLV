"""Portable notebook runner. --prepare-only never executes the PMP solver cell."""

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent


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
        from scenario_project import audit_project
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
    main()
