"""Public foreground correction and observable-only background workflow tests."""
import importlib
import json

import numpy as np
import pytest

from adctoolbox import (apply_calibration, build_calibration_features,
                       fit_calibration_polynomial, fit_calibration_mlp,
                       DitherGainTracker, apply_gain_calibration, fit_pipeline_gain_sine)


def test_history_streaming_matches_whole_record_and_does_not_invent_startup():
    x = np.arange(46.).reshape(23, 2)
    whole = build_calibration_features(x, history=3)
    state, parts, indices, start = None, [], [], 0
    for size in [1, 1, 5, 3, 13]:
        result = build_calibration_features(x[start:start+size], history=3, state=state)
        state = result['state']
        parts.append(result['features'])
        indices.extend(result['sample_indices']+start)
        start += size
    np.testing.assert_array_equal(np.vstack(parts), whole['features'])
    np.testing.assert_array_equal(indices, whole['sample_indices'])
    np.testing.assert_array_equal(whole['features'][0], x[[3, 2, 1, 0]].ravel())
    restarted = build_calibration_features(x[:2], history=3)
    assert restarted['features'].shape == (0, 8)


def test_polynomial_recovers_cross_terms_and_json_round_trip():
    rng = np.random.default_rng(7)
    x = rng.uniform(-1, 1, (500, 2))
    target = .2+1.3*x[:, 0]-.1*x[:, 1]**2+.07*x[:, 0]*x[:, 1]**2
    fitted = fit_calibration_polynomial(x, target, degree=3, ridge=0)
    model = json.loads(json.dumps(fitted['model'], allow_nan=False))
    xt = rng.uniform(-.9, .9, (100, 2))
    truth = .2+1.3*xt[:, 0]-.1*xt[:, 1]**2+.07*xt[:, 0]*xt[:, 1]**2
    np.testing.assert_allclose(apply_calibration(xt, model)['calibrated_signal'], truth, atol=2e-14)
    assert fitted['diagnostics']['design_rank'] == 10
    assert not fitted['diagnostics']['rank_deficient']


def test_rank_and_extrapolation_are_reported_without_hidden_clipping():
    x = np.linspace(-1, 1, 100)
    result = fit_calibration_polynomial(np.c_[x, x], x, degree=2)
    assert result['diagnostics']['rank_deficient']
    applied = apply_calibration([[2, 2]], result['model'])
    assert applied['outside_training_range'][0]
    assert applied['calibrated_signal'][0] > 1.9


def test_mlp_generalizes_and_selects_validation_best_with_frozen_normalization():
    x = np.linspace(-.9, .9, 320)
    val = np.linspace(-.88, .88, 113)
    raw = x+.08*x**3
    args = dict(validation_features=val+.08*val**3, validation_reference=val,
                hidden_units=8, max_iterations=120, seed=71)
    result = fit_calibration_mlp(raw, x, **args)
    np.testing.assert_allclose(result['model']['input_mean'], [raw.mean()], atol=1e-16)
    chosen = result['history'][result['diagnostics']['selected_iteration']]
    assert chosen['validation_mse'] == min(row['validation_mse'] for row in result['history'])
    test = np.linspace(-.86, .86, 127)
    model = json.loads(json.dumps(result['model'], allow_nan=False))
    pred = apply_calibration(test+.08*test**3, model)['calibrated_signal']
    assert np.sqrt(np.mean((pred-test)**2)) < 3e-4
    original = json.dumps(model, sort_keys=True)
    apply_calibration([5.], model)
    assert json.dumps(model, sort_keys=True) == original


@pytest.mark.parametrize('x,y', [([1., np.nan], [1., 2.]), ([1., 2.], [1.]), ([], [])])
def test_bad_training_data_rejected(x, y):
    with pytest.raises(ValueError):
        fit_calibration_polynomial(x, y)


def test_model_and_history_contracts():
    with pytest.raises(ValueError):
        build_calibration_features([1, 2], history=-1)
    with pytest.raises(ValueError):
        build_calibration_features([1, 2], history=1, state=[[1, 2]])
    with pytest.raises(ValueError):
        fit_calibration_polynomial(np.ones((5, 20)), np.ones(5), degree=8)
    model = fit_calibration_polynomial([1, 2, 3], [2, 4, 6], degree=1)['model']
    with pytest.raises(ValueError):
        apply_calibration([[1, 2]], model)
    model['input_scale'] = [0]
    with pytest.raises(ValueError):
        apply_calibration([1], model)


def test_public_gain_tracker_is_legacy_example_tracker():
    legacy = importlib.import_module('adctoolbox.examples.11_calibration.pipeline_dither_model')
    assert legacy.DitherGainTracker is DitherGainTracker
    assert legacy.fit_foreground_gain is fit_pipeline_gain_sine


def test_hybrid_gain_snapshot_reset_and_hold():
    tracker = DitherGainTracker(initial_gain=3.9, learning_rate=1)
    p = np.tile([-1., 1.], 100)
    r = 4.1*.0625*p
    codes = np.floor((r+1)*2048).astype(int)
    before = tracker.apply(np.zeros(len(p)), r, p)
    assert before['gain_used'] == 3.9
    update = tracker.update(r, p, codes)
    assert update['gain_next'] == pytest.approx(4.1)
    assert before['gain_used'] == 3.9
    np.testing.assert_allclose(tracker.apply(np.zeros(len(p)), r, p)['calibrated_signal'], 0, atol=1e-15)
    tracker.update(r, p, np.zeros(len(p)))
    assert tracker.updates == 1
    tracker.reset()
    assert tracker.gain_estimate == 3.9 and tracker.updates == 0


def test_foreground_qr_fit_is_capture_partition_invariant():
    n = np.arange(8192)
    f = 137/8192
    x = .8*np.sin(2*np.pi*f*n+.71)
    q = (np.searchsorted(np.arange(-5, 6, 2)/8, x)-3)/4
    r = 3.88*(x-q)
    capture = {'coarse': q, 'backend': r, 'pn': np.zeros(len(n))}
    whole = fit_pipeline_gain_sine([capture], f)
    pieces = [{key: value[i:i+113] for key, value in capture.items()} for i in range(0, len(n), 113)]
    streamed = fit_pipeline_gain_sine(pieces, f)
    assert whole['gain_estimate'] == pytest.approx(3.88, abs=1e-12)
    assert streamed['gain_estimate'] == pytest.approx(whole['gain_estimate'], abs=1e-12)
    np.testing.assert_allclose(apply_gain_calibration(q, r, np.zeros(len(n)), gain_estimate=3.88,
                                                    probe_amplitude=.0625)['calibrated_signal'], x, atol=1e-15)
    np.testing.assert_allclose(apply_gain_calibration(q, r, np.zeros(len(n)), gain_estimate=3.88,
                                                    probe_amplitude=0.)['calibrated_signal'], x, atol=1e-15)


def test_foreground_rejects_no_excitation_or_nonzero_probe():
    with pytest.raises(ValueError):
        fit_pipeline_gain_sine([], .1)
    c = {'coarse': np.zeros(100), 'backend': np.zeros(100), 'pn': np.zeros(100)}
    with pytest.raises(ValueError):
        fit_pipeline_gain_sine([c], .1)
    c['pn'][:] = 1
    with pytest.raises(ValueError):
        fit_pipeline_gain_sine([c], .1)


def test_frontend_state_partition_and_reference_channel_are_explicit():
    fb = importlib.import_module('adctoolbox.examples.11_calibration.foreground_benchmark')
    config = fb.FrontendConfig()
    x = .8*np.sin(.7*np.arange(1024))
    whole = fb.NonlinearFrontend(config, 11).convert(x)
    adc = fb.NonlinearFrontend(config, 11)
    parts = [adc.convert(x[:317]), adc.convert(x[317:])]
    np.testing.assert_array_equal(np.r_[parts[0]['raw'], parts[1]['raw']], whole['raw'])
    biased = fb.capture(fb.FrontendConfig(monitor_gain=.9), size=2048, seed=11,
                        frequencies=[137/2048], amplitudes=[.8], phases=[.2])
    # The fitting label comes from the configured monitor, not silently from truth.
    assert np.std(biased['reference'])/np.std(biased['truth']) == pytest.approx(.9, abs=1e-4)


def test_foreground_cli_exports_models_independent_splits_and_refuses_overwrite(tmp_path):
    ex = importlib.import_module('adctoolbox.examples.11_calibration.exp_cal03_foreground_nonlinear')
    argv = ['--output', str(tmp_path), '--size', '1024', '--records', '4',
            '--validation-records', '2', '--iterations', '3', '--stride', '8',
            '--seeds', '11', '--plants', 'static']
    ex.main(argv)
    manifest = json.loads((tmp_path/'static_seed11/data_manifest.json').read_text())
    train = {r['tone_bin'] for r in manifest['training']}
    val = {r['tone_bin'] for r in manifest['validation']}
    tests = {k for c in manifest['tests'] for k in c['bins']}
    assert not train & val and not train & tests and not val & tests
    models = json.loads((tmp_path/'static_seed11/models.json').read_text())
    assert set(models) >= {'poly5_history', 'mlp_history', 'poly5_output_fit'}
    assert (tmp_path/'foreground_comparison.png').stat().st_size > 1000
    with pytest.raises(SystemExit):
        ex.main(argv)


def test_hybrid_initializes_from_foreground_then_tracks_causally(tmp_path):
    from argparse import Namespace
    ex = importlib.import_module('adctoolbox.examples.11_calibration.exp_cal04_hybrid_tracking')
    args = Namespace(output=tmp_path, blocks=128, block_size=8192, foreground_blocks=4)
    rows, summary = ex.run_case(args, scenario='step', waveform='sine', seed=11)
    assert rows[0]['hybrid_gain_used'] == rows[0]['foreground_gain']
    assert rows[0]['hybrid_spectral_ratio_db'] == rows[0]['foreground_frozen_spectral_ratio_db']
    for name in ('hybrid', 'background'):
        for previous, current in zip(rows, rows[1:]):
            assert current[name+'_gain_used'] == previous[name+'_gain_next']
    tail = {r['method']: r['spectral_ratio_db'] for r in summary if r['window'] == 'final_quarter'}
    assert tail['hybrid'] > tail['foreground_frozen']+15
    assert sum(r['backend_overloads'] for r in rows) == 0


def test_acceptance_audit_replays_models_and_checks_background_artifacts(tmp_path):
    fg = importlib.import_module('adctoolbox.examples.11_calibration.exp_cal03_foreground_nonlinear')
    bg = importlib.import_module('adctoolbox.examples.11_calibration.exp_cal04_hybrid_tracking')
    audit = importlib.import_module('adctoolbox.examples.11_calibration.audit_calibration_acceptance')
    excitation = importlib.import_module('adctoolbox.examples.11_calibration.exp_cal05_foreground_excitation')
    foreground, hybrid = tmp_path/'fg', tmp_path/'hybrid'
    fg.main(['--output', str(foreground), '--size', '1024', '--records', '4',
             '--validation-records', '2', '--iterations', '3', '--stride', '8',
             '--seeds', '11', '--plants', 'static'])
    bg.main(['--output', str(hybrid), '--blocks', '64', '--block-size', '1024',
             '--foreground-blocks', '2', '--seeds', '11', '--scenarios', 'constant', '--waveforms', 'sine'])
    path = tmp_path/'audit.json'
    control = tmp_path/'excitation'
    excitation.main(['--baseline', str(foreground), '--output', str(control)])
    audit.main(['--foreground', str(foreground), '--hybrid', str(hybrid), '--excitation', str(control), '--output', str(path)])
    result = json.loads(path.read_text())
    assert result['status'] == 'passed'
    assert result['foreground']['frozen_model_metric_rows_replayed'] == 180
    assert result['hybrid']['causal_blocks_checked'] == 64
    assert result['excitation']['mixed_model_metric_rows_replayed'] == 80
    assert (foreground/'source_snapshot/foreground.py').is_file()
    with pytest.raises(SystemExit):
        audit.main(['--foreground', str(foreground), '--hybrid', str(hybrid), '--output', str(path)])
