"""Plots and cooling accounting from the scenario's validated thermal output."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.ticker import MaxNLocator
from scenario_plot_style import IEEE_RC, IEEE_DPI, column_size, save_ieee_figure


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
