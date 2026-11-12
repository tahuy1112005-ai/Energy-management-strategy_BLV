"""Shared print styling; no simulation or assessment calculations."""

from pathlib import Path

import matplotlib.pyplot as plt


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
