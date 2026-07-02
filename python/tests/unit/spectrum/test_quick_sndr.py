"""
Unit tests for quick_sndr: lean SNDR-only path.

Validates:
  1. SNDR/ENOB match analyze_spectrum within rounding on an ideal sine.
  2. Bare-defaults call works (just data + fs).
  3. Window override is honored.
"""
import importlib

import numpy as np
import pytest

from adctoolbox import quick_sndr, analyze_spectrum
from adctoolbox.spectrum.compute_spectrum import compute_spectrum
from adctoolbox.spectrum._window import _get_default_side_bin


def _ideal_quantized_sine(n_samples=256, n_bits=16, bin_index=7):
    n = np.arange(n_samples)
    x = np.sin(2 * np.pi * bin_index * n / n_samples)
    full_scale = (1 << (n_bits - 1)) - 1
    codes = np.round(x * full_scale).astype(np.int64)
    codes = np.clip(codes, -(1 << (n_bits - 1)), full_scale)
    return codes / (1 << (n_bits - 1))


def _noncoherent_sine_with_noise(n_samples=8192, bin_index=983.37, noise_rms=1e-4):
    n = np.arange(n_samples)
    rng = np.random.default_rng(1234)
    return np.sin(2 * np.pi * bin_index * n / n_samples) + noise_rms * rng.standard_normal(n_samples)


def _detected_side_bin(compute_result):
    plot_data = compute_result['plot_data']
    return (plot_data['sig_bin_end'] - plot_data['sig_bin_start'] - 1) // 2


def test_quick_sndr_matches_analyze_spectrum_on_ideal_sine():
    aout = _ideal_quantized_sine()
    fs = 12.5e6

    q = quick_sndr(aout, fs=fs)
    a = analyze_spectrum(aout, fs=fs, create_plot=False)

    # SNDR comes from same formula in both — should match to <0.01 dB.
    assert abs(q['sndr_dbc'] - a['sndr_dbc']) < 0.1, (
        f"quick_sndr SNDR={q['sndr_dbc']:.3f} vs analyze_spectrum SNDR="
        f"{a['sndr_dbc']:.3f}"
    )
    assert abs(q['enob'] - a['enob']) < 0.02


def test_quick_sndr_matches_compute_spectrum_with_explicit_side_bin():
    aout = _ideal_quantized_sine(n_samples=1024, bin_index=37)
    fs = 12.5e6

    q = quick_sndr(aout, fs=fs, win_type='hann', side_bin=1)
    c = compute_spectrum(aout, fs=fs, win_type='hann', side_bin=1)

    assert abs(q['sndr_dbc'] - c['metrics']['sndr_dbc']) < 1e-9
    assert abs(q['enob'] - c['metrics']['enob']) < 1e-9


def test_quick_sndr_default_matches_compute_spectrum_coherent_default():
    aout = _ideal_quantized_sine(n_samples=1024, bin_index=37)
    fs = 12.5e6
    side_bin = _get_default_side_bin('hann')

    q = quick_sndr(aout, fs=fs, win_type='hann')
    c = compute_spectrum(aout, fs=fs, win_type='hann', side_bin=side_bin)

    assert abs(q['sndr_dbc'] - c['metrics']['sndr_dbc']) < 1e-9
    assert abs(q['enob'] - c['metrics']['enob']) < 1e-9


def test_quick_sndr_auto_matches_compute_spectrum_auto_side_bin():
    aout = _noncoherent_sine_with_noise()
    fs = 100e6

    q = quick_sndr(aout, fs=fs, win_type='hann', side_bin="auto", max_scale_range=[-1, 1])
    c = compute_spectrum(aout, fs=fs, win_type='hann', side_bin=None, max_scale_range=[-1, 1])

    assert _detected_side_bin(c) > _get_default_side_bin('hann')
    assert abs(q['sndr_dbc'] - c['metrics']['sndr_dbc']) < 1e-9
    assert abs(q['enob'] - c['metrics']['enob']) < 1e-9


def test_quick_sndr_auto_is_explicit_opt_in_for_noncoherent_captures():
    aout = _noncoherent_sine_with_noise()

    q_default = quick_sndr(aout, win_type='hann', max_scale_range=[-1, 1])
    q_auto = quick_sndr(aout, win_type='hann', side_bin="auto", max_scale_range=[-1, 1])

    assert q_auto['sndr_dbc'] > q_default['sndr_dbc'] + 20.0


def test_quick_sndr_keeps_direct_fft_fast_path():
    quick_sndr_module = importlib.import_module('adctoolbox.spectrum.quick_sndr')

    assert 'compute_spectrum' not in quick_sndr_module.__dict__


def test_quick_sndr_bare_call():
    """Sanity: just data, no kwargs, returns the dict."""
    aout = _ideal_quantized_sine()
    result = quick_sndr(aout)
    assert set(result.keys()) == {'sndr_dbc', 'enob'}
    assert result['sndr_dbc'] > 90  # 16-bit ideal ≈ 98 dB


def test_quick_sndr_window_override():
    """Rectangular window matches analyze_spectrum's rectangular path."""
    aout = _ideal_quantized_sine()
    q = quick_sndr(aout, fs=12.5e6, win_type='rectangular')
    a = analyze_spectrum(aout, fs=12.5e6, win_type='rectangular', create_plot=False)
    assert abs(q['sndr_dbc'] - a['sndr_dbc']) < 0.1


def test_quick_sndr_preserves_numeric_side_bin_coercion():
    aout = _ideal_quantized_sine(n_samples=1024, bin_index=37)

    assert quick_sndr(aout, side_bin=3.9) == quick_sndr(aout, side_bin=3)
    assert quick_sndr(aout, side_bin=-2) == quick_sndr(aout, side_bin=0)


@pytest.mark.parametrize("side_bin", ["bad", "3"])
def test_quick_sndr_preserves_non_auto_string_rejection(side_bin):
    aout = _ideal_quantized_sine(n_samples=1024, bin_index=37)

    with pytest.raises(TypeError):
        quick_sndr(aout, side_bin=side_bin)
