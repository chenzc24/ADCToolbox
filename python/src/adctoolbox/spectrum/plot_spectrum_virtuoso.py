"""
Cadence Virtuoso / ADE Explorer style spectrum plot.

Dark canvas, red stem bars per FFT bin, fine dotted grid.  Same set of
annotations as the analyzer-style plotter (fundamental marker, max-spur
diamond, harmonic squares, metrics text block, NSD line) but recolored
for the dark theme:

    - stems      : red          ('1 stem = 1 bin' Virtuoso convention)
    - fundamental: yellow dot + "Sig = X dB"
    - max spur   : yellow diamond + "MaxSpur"
    - harmonics  : cyan squares + cyan order numbers (2, 3, ...)
    - metric box : white text
    - NSD line   : yellow dashed
    - OSR line   : dim white dashed

Mirrors `plot_spectrum.py`'s structure so the two stay in lock-step
when the underlying metrics / plot_data layout evolves.
"""

import numpy as np
import matplotlib.pyplot as plt


# Color palette — single place to retune the dark theme
_C_STEM   = '#ff3030'   # red, slightly brighter than 'r' for visibility on black
_C_FUND   = '#ffd000'   # warm yellow — fundamental + spur (loud-and-clear)
_C_HARM   = '#00e5ff'   # cyan — harmonics (distinct from fundamental)
_C_METRIC = 'white'     # metric text block
_C_NSD    = '#ffd000'   # NSD line — match fundamental color
_C_OSR    = '#999999'   # dim white — OSR cutoff line
_C_COH    = '#ffe680'   # light yellow — coherent gain note
_C_WARN   = '#ffa500'   # orange — collision warning


def plot_spectrum_virtuoso(compute_results, show_title=True, show_label=True,
                           plot_harmonics_up_to=3, ax=None, baseline_db=None):
    """
    Virtuoso/ADE-Explorer style spectrum plot with annotations.

    Parameters
    ----------
    compute_results : dict
        Output of `compute_spectrum`.
    show_title : bool
        Show auto-generated plot title.
    show_label : bool
        Add fundamental marker, spur marker, harmonics markers, and the
        metric text block.  Set False for a bare-stem look.
    plot_harmonics_up_to : int
        Highlight harmonics up to this order (HD2..HDk).
    ax : matplotlib.axes.Axes, optional
        Target axes.  If None, uses current axes.  Axes + figure facecolor
        will be set to black.
    baseline_db : float, optional
        Bottom of stem bars in dB.  None → adaptive (min(spec) - 5).
    """
    metrics    = compute_results['metrics']
    plot_data  = compute_results['plot_data']
    spec_db    = plot_data['power_spectrum_db_plot']
    freq       = plot_data['freq']
    fundamental_bin = plot_data['fundamental_bin']
    spur_bin_idx    = plot_data['spur_bin_idx']
    spur_db         = spec_db[spur_bin_idx]
    is_coherent     = plot_data.get('is_coherent', False)
    collided_harmonics = plot_data.get('collided_harmonics', [])
    harmonic_bins      = plot_data.get('harmonic_bins', [])
    harmonics_dbc      = metrics.get('harmonics_dbc', [])

    N    = compute_results['N']
    M    = compute_results['M']
    fs   = compute_results['fs']
    osr  = compute_results['osr']
    Nd2_inband = len(freq) // osr
    v_offset = plot_data.get('v_offset', 0.0)
    nf_line_level = metrics['nsd_dbfs_hz'] + 10 * np.log10(fs / N) + v_offset

    if ax is None:
        ax = plt.gca()
    fig = ax.figure

    # ---- Dark theme: black canvas, white annotations -----------------
    fig.set_facecolor('black')
    ax.set_facecolor('black')
    for spine in ax.spines.values():
        spine.set_color('white')
    ax.tick_params(axis='both', which='both', colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')

    # ---- Stem bars ---------------------------------------------------
    if baseline_db is None:
        baseline_db = float(np.min(spec_db)) - 5.0
    ax.vlines(freq, baseline_db, spec_db, colors=_C_STEM, linewidth=0.8)

    # ---- Grid --------------------------------------------------------
    ax.minorticks_on()
    ax.grid(True, which='major', linestyle=':', color='white', alpha=0.35, linewidth=0.6)
    ax.grid(True, which='minor', linestyle=':', color='white', alpha=0.15, linewidth=0.4)

    # ---- Adaptive y-axis (same logic as plot_spectrum.py) ------------
    minx = -100
    for threshold in [-100, -120, -140, -160, -180]:
        below = np.sum(spec_db[:Nd2_inband] < threshold)
        if below / max(len(spec_db[:Nd2_inband]), 1) * 100 > 5.0:
            minx = threshold - 20
        else:
            break
    minx = max(minx, -200)
    minx = min(minx, baseline_db)            # never crop below the stems
    ax.set_xlim(fs / N, fs / 2)
    ax.set_ylim(minx, 0)

    # ---- Labels ------------------------------------------------------
    ax.set_xlabel('freq (Hz)')
    ax.set_ylabel('(dB)')
    if show_title:
        ax.set_title('Power Spectrum')

    if not show_label:
        return

    # ---- Fundamental marker + "Sig" text -----------------------------
    ax.plot(freq[fundamental_bin], spec_db[fundamental_bin],
            'o', color=_C_FUND, markersize=8)

    # ---- Harmonic markers --------------------------------------------
    if plot_harmonics_up_to > 0 and len(harmonic_bins) and len(harmonics_dbc):
        for idx in range(len(harmonics_dbc)):
            order = idx + 2                  # HD2, HD3, ...
            if order > plot_harmonics_up_to or order in collided_harmonics:
                continue
            bin_center = harmonic_bins[idx]
            ax.plot(bin_center * fs / N, spec_db[bin_center],
                    's', color=_C_HARM, markersize=5)
            ax.text(bin_center * fs / N, spec_db[bin_center] + 3, str(order),
                    color=_C_HARM, fontsize=11, ha='center')

    # ---- Max-spur diamond + "MaxSpur" text ---------------------------
    ax.plot(spur_bin_idx / N * fs, spur_db,
            'd', color=_C_FUND, markersize=5)
    ax.text(spur_bin_idx / N * fs, spur_db + 10, 'MaxSpur',
            color=_C_FUND, fontsize=10, ha='center')

    # ---- Text-block positioning (mirrors plot_spectrum.py) -----------
    if osr > 1:
        TX = 10 ** (np.log10(fs) * 0.01 + np.log10(fs / N) * 0.99)
    else:
        TX = fs * 0.3 if fundamental_bin / N < 0.2 else fs * 0.01
    TYD = minx * 0.06

    def _fmt_freq(f):
        if f >= 1e9: return f'{f/1e9:.1f}G'
        if f >= 1e6: return f'{f/1e6:.1f}M'
        if f >= 1e3: return f'{f/1e3:.1f}K'
        return f'{f:.1f}'

    Fin = fundamental_bin / N * fs

    ax.text(freq[fundamental_bin], spec_db[fundamental_bin] - 4,
            f'Sig = {metrics["sig_pwr_dbfs"]:.2f} dB',
            color=_C_FUND, fontsize=10)

    metric_lines = [
        f'Fin/fs = {_fmt_freq(Fin)} / {_fmt_freq(fs)} Hz',
        f'ENoB = {metrics["enob"]:.2f}',
        f'SNDR = {metrics["sndr_dbc"]:.2f} dB',
        f'SFDR = {metrics["sfdr_dbc"]:.2f} dB',
        f'THD = {metrics["thd_dbc"]:.2f} dB',
        f'SNR = {metrics["snr_dbc"]:.2f} dB',
        f'Noise Floor = {metrics["noise_floor_dbfs"]:.2f} dB',
        f'NSD = {metrics["nsd_dbfs_hz"]:.2f} dBFS/Hz',
    ]
    for i, line in enumerate(metric_lines, start=1):
        ax.text(TX, TYD * i, line, color=_C_METRIC, fontsize=10)

    # ---- NSD baseline line -------------------------------------------
    if osr > 1:
        ax.semilogx([fs / N, fs / 2 / osr],
                    [nf_line_level, nf_line_level],
                    '--', color=_C_NSD, linewidth=1)
        ax.text(TX, TYD * 9, f'OSR = {osr:.2f}', color=_C_METRIC, fontsize=10)
        ax.plot([fs / 2 / osr, fs / 2 / osr], [0, -1000],
                '--', color=_C_OSR, linewidth=1)
    else:
        ax.plot([0, fs / 2], [nf_line_level, nf_line_level],
                '--', color=_C_NSD, linewidth=1)

    # ---- Optional gain / collision notes -----------------------------
    next_row = 10 if osr > 1 else 9
    if is_coherent and M > 1:
        coh_gain_db = 10 * np.log10(M)
        ax.text(TX, TYD * next_row, f'*Coherent Gain = {coh_gain_db:.2f} dB',
                color=_C_COH, fontsize=10)
        next_row += 1
    if collided_harmonics:
        collision_str = ', '.join(f'HD{h}' for h in sorted(collided_harmonics))
        ax.text(TX, TYD * next_row, f'*Collided with fundamental: {collision_str}',
                color=_C_WARN, fontsize=10)
