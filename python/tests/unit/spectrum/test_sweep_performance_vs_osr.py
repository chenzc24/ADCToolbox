"""Unit tests for sweep_performance_vs_osr."""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytest

from adctoolbox import find_coherent_frequency, sweep_performance_vs_osr
from adctoolbox.spectrum.compute_spectrum import compute_spectrum
from adctoolbox.spectrum._bin_ranges import rfft_inband_bin_count
from adctoolbox.spectrum.sweep_performance_vs_osr import _one_sided_rms_power_spectrum


def _legend_labels(ax):
    legend = ax.get_legend()
    assert legend is not None
    return [text.get_text() for text in legend.get_texts()]


def _assert_performance_axis(ax):
    assert ax.get_xlabel() == 'OSR'
    assert ax.get_ylabel() == 'SNDR / SFDR (dB)'
    assert ax.get_title() == 'Performance vs OSR'
    assert ax.get_xscale() == 'log'
    assert len(ax.lines) >= 2
    assert {'SNDR (ENOB)', 'SFDR'}.issubset(_legend_labels(ax))


def _assert_enob_axis(ax):
    assert ax.get_ylabel() == 'ENOB (bits)'
    ymin, ymax = ax.get_ylim()
    assert ymin < ymax


def _coherent_sine_with_noise(n=8192, fs=100e6, fin_target=12e6, amplitude=0.5, noise_rms=1e-3):
    fin, _ = find_coherent_frequency(fs, fin_target, n)
    t = np.arange(n) / fs
    rng = np.random.default_rng(123)
    return amplitude * np.sin(2 * np.pi * fin * t) + noise_rms * rng.standard_normal(n), fs, fin


def test_one_sided_rms_power_spectrum_matches_time_domain_rms():
    rng = np.random.default_rng(0)

    for n in (1024, 1025):
        data = rng.normal(size=n)
        spectrum = _one_sided_rms_power_spectrum(data)

        assert np.sum(spectrum) == pytest.approx(np.mean(data ** 2), rel=1e-12, abs=1e-15)


def test_clean_sine_high_sndr():
    """Clean sine: SNDR should be very high at all OSR."""
    N = 1024
    t = np.arange(N)
    freq = 0.1
    sig = 0.5 * np.sin(2 * np.pi * freq * t)

    osr_values = np.array([2, 4, 8, 16, 32])
    result = sweep_performance_vs_osr(sig, osr=osr_values, create_plot=False)

    assert isinstance(result, dict)
    assert 'osr' in result
    assert 'sndr' in result
    assert 'sfdr' in result
    assert 'enob' in result
    assert len(result['sndr']) == len(osr_values)

    # Clean sine should have very high SNDR (> 80 dB)
    assert np.all(result['sndr'] > 80)
    plt.close('all')


def test_noisy_sine_sndr_increases_with_osr():
    """Sine + white noise: SNDR should increase with OSR (~3 dB per doubling)."""
    rng = np.random.default_rng(42)
    N = 4096
    t = np.arange(N)
    freq = 0.05
    sig = 0.5 * np.sin(2 * np.pi * freq * t)
    noise = rng.normal(0, 0.01, N)
    data = sig + noise

    osr_values = np.array([2, 4, 8, 16, 32, 64])
    result = sweep_performance_vs_osr(data, osr=osr_values, create_plot=False)

    # SNDR should generally increase with OSR
    # Check that highest OSR has higher SNDR than lowest
    assert result['sndr'][-1] > result['sndr'][0]

    # ENOB should be positive
    assert np.all(result['enob'] > 0)
    plt.close('all')


def test_sweep_sndr_matches_compute_spectrum_for_white_noise_osr_one():
    data, fs, _ = _coherent_sine_with_noise()

    sweep = sweep_performance_vs_osr(data, osr=np.array([1]), create_plot=False)
    spectrum = compute_spectrum(
        data,
        fs=fs,
        win_type='hann',
        side_bin=1,
        osr=1,
        nf_method=3,
        max_scale_range=[-1, 1],
    )

    assert sweep['sndr'][0] == pytest.approx(spectrum['metrics']['sndr_dbc'], abs=0.15)


def test_sweep_harmonic_residual_sndr_uses_rms_power_scale():
    n = 8192
    fs = 100e6
    fin, _ = find_coherent_frequency(fs, 12e6, n)
    t = np.arange(n) / fs
    amplitude = 0.5
    hd2 = amplitude * 10 ** (-60 / 20)
    data = amplitude * np.sin(2 * np.pi * fin * t) + hd2 * np.sin(2 * np.pi * 2 * fin * t)

    result = sweep_performance_vs_osr(data, osr=np.array([1]), create_plot=False)

    assert result['sndr'][0] == pytest.approx(60.0, abs=0.05)


def test_single_point_osr_matches_same_osr_in_multi_point_sweep():
    data, _, _ = _coherent_sine_with_noise(noise_rms=2e-3)

    single = sweep_performance_vs_osr(data, osr=np.array([4]), create_plot=False)
    sweep = sweep_performance_vs_osr(data, osr=np.array([2, 4, 8, 16]), create_plot=False)
    idx = int(np.where(sweep['osr'] == 4)[0][0])

    assert single['sndr'][0] == sweep['sndr'][idx]
    assert single['sfdr'][0] == sweep['sfdr'][idx]
    assert single['enob'][0] == sweep['enob'][idx]


def test_default_osr():
    """Default OSR (no osr argument) should work."""
    N = 256
    t = np.arange(N)
    sig = 0.5 * np.sin(2 * np.pi * 0.1 * t)

    result = sweep_performance_vs_osr(sig, create_plot=False)
    assert len(result['osr']) == N // 2
    assert len(result['sndr']) == N // 2
    plt.close('all')


def test_default_osr_maps_to_each_positive_rfft_bin_count():
    """Default OSR should sweep every possible non-DC in-band upper edge."""
    N = 33
    t = np.arange(N)
    sig = 0.5 * np.sin(2 * np.pi * 3 * t / N)

    result = sweep_performance_vs_osr(sig, create_plot=False)

    expected_n_bins = N // 2
    expected_osr = (N / 2) / np.arange(expected_n_bins, 0, -1)
    expected_counts = np.arange(expected_n_bins + 1, 1, -1)
    actual_counts = np.array([
        rfft_inband_bin_count(N, osr)
        for osr in result['osr']
    ])

    assert len(result['osr']) == expected_n_bins
    np.testing.assert_allclose(result['osr'], expected_osr)
    np.testing.assert_array_equal(actual_counts, expected_counts)
    plt.close('all')


def test_plot_with_ax():
    """Providing ax should produce single-axis plot without error."""
    N = 512
    t = np.arange(N)
    sig = 0.5 * np.sin(2 * np.pi * 0.1 * t)
    osr = np.array([2, 4, 8])

    fig, ax = plt.subplots()
    result = sweep_performance_vs_osr(sig, osr=osr, ax=ax)

    np.testing.assert_array_equal(result['osr'], osr)
    assert len(result['sndr']) == len(osr)
    assert fig.axes[0] is ax
    assert len(fig.axes) == 2
    _assert_performance_axis(ax)
    _assert_enob_axis(fig.axes[1])
    plt.close(fig)


def test_plot_auto_subplots():
    """No ax provided should create 2-subplot figure."""
    plt.close('all')
    N = 512
    rng = np.random.default_rng(0)
    t = np.arange(N)
    sig = 0.5 * np.sin(2 * np.pi * 0.1 * t) + rng.normal(0, 0.01, N)

    result = sweep_performance_vs_osr(sig, osr=np.array([2, 4, 8, 16]))
    fig = plt.gcf()
    main_axes = [ax for ax in fig.axes if ax.get_title() == 'Performance vs OSR']
    slope_axes = [ax for ax in fig.axes if ax.get_ylabel() == 'SNDR Slope (dB/decade)']
    enob_axes = [ax for ax in fig.axes if ax.get_ylabel() == 'ENOB (bits)']

    assert len(result['osr']) == 4
    assert len(fig.axes) == 3
    assert len(main_axes) == 1
    assert len(slope_axes) == 1
    assert len(enob_axes) == 1
    _assert_performance_axis(main_axes[0])
    _assert_enob_axis(enob_axes[0])
    assert slope_axes[0].get_xlabel() == 'OSR'
    assert slope_axes[0].get_xscale() == 'log'
    assert len(slope_axes[0].lines) >= 2
    assert any(text.get_text() == 'White Noise Limit' for text in slope_axes[0].texts)
    plt.close(fig)


def test_enob_formula():
    """ENOB should follow (SNDR - 1.76) / 6.02."""
    N = 512
    t = np.arange(N)
    sig = 0.5 * np.sin(2 * np.pi * 0.1 * t)

    result = sweep_performance_vs_osr(sig, osr=np.array([4, 8]), create_plot=False)
    expected_enob = (result['sndr'] - 1.76) / 6.02
    np.testing.assert_allclose(result['enob'], expected_enob, atol=1e-10)
    plt.close('all')
