"""Compare frozen foreground, nominal-start background, and hybrid tracking.

The hybrid estimate is initialized by a separate probe-off sine calibration.
Both trackers see identical normal-operation captures and apply their parameter
snapshot BEFORE updating. No evaluator truth enters either estimator.
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'

import argparse
import hashlib
import inspect
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from adctoolbox import DitherGainTracker, apply_gain_calibration
try:
    from . import pipeline_dither_model as plant
    from . import exp_cal01_dither_background as baseline
    from .exp_cal03_foreground_nonlinear import write_json, write_csv
except ImportError:
    import pipeline_dither_model as plant
    import exp_cal01_dither_background as baseline
    from exp_cal03_foreground_nonlinear import write_json, write_csv


METHODS = ('nominal', 'foreground_frozen', 'background', 'hybrid', 'oracle', 'foreground_probe_off')


def run_case(args, *, scenario, waveform, seed):
    config = plant.PipelineConfig()
    fg = baseline.foreground_fit(config, seed, args.block_size, args.foreground_blocks)
    trackers = {'background': DitherGainTracker(), 'hybrid': DitherGainTracker(initial_gain=fg['gain_estimate'])}
    adc, off_adc = plant.DitherPipeline(config, seed), plant.DitherPipeline(config, seed)
    rows = []
    for block in range(args.blocks):
        indices = np.arange(block*args.block_size, (block+1)*args.block_size)
        clean, bins = baseline.waveform(indices, args.block_size, waveform)
        gain = baseline.gain_trajectory(indices, args.blocks*args.block_size, scenario)
        c = adc.convert(clean, gain)
        off = off_adc.convert(clean, gain, probe_enabled=False)
        row = {'block': block, 'time_ms': (block+1)*args.block_size/baseline.FS*1e3,
               'true_gain_mean': float(gain.mean()), 'foreground_gain': fg['gain_estimate'],
               'backend_overloads': c['backend_overloads'], 'probe_off_overloads': off['backend_overloads']}
        predictions = {name: apply_gain_calibration(c['coarse'], c['backend'], c['pn'],
                       gain_estimate=g, probe_amplitude=config.probe_amplitude)['calibrated_signal']
                       for name, g in [('nominal', 4.), ('foreground_frozen', fg['gain_estimate'])]}
        for name, tracker in trackers.items():
            applied = tracker.apply(c['coarse'], c['backend'], c['pn'])
            predictions[name] = applied['calibrated_signal']
            row[name+'_gain_used'] = applied['gain_used']
            row[name+'_relative_error_rms'] = float(np.sqrt(np.mean((applied['gain_used']/gain-1)**2)))
            updated = tracker.update(c['backend'], c['pn'], c['backend_code'])
            row[name+'_gain_next'], row[name+'_status'] = updated['gain_next'], updated['status']
        predictions['oracle'] = c['coarse']+c['backend']/gain-config.probe_amplitude*c['pn']
        predictions['foreground_probe_off'] = off['coarse']+off['backend']/fg['gain_estimate']
        for name, prediction in predictions.items():
            row.update({name+'_'+k: v for k, v in baseline.metrics(prediction, clean, bins).items()})
        rows.append(row)
    directory = args.output/f'{waveform}_{scenario}_seed{seed}'
    directory.mkdir()
    write_csv(directory/'trajectory.csv', rows)
    windows = {'first_16_blocks': rows[:16], 'final_quarter': rows[3*args.blocks//4:]}
    if scenario == 'ramp':
        windows['active_ramp'] = rows[args.blocks//4:3*args.blocks//4]
    if scenario == 'step':
        windows['first_16_after_step'] = rows[args.blocks//2:args.blocks//2+16]
    summary = []
    for window, records in windows.items():
        for name in METHODS:
            summary.append({'waveform': waveform, 'scenario': scenario, 'seed': seed, 'window': window, 'method': name,
                            **{k: float(np.mean([r[name+'_'+k] for r in records])) for k in
                               ('spectral_ratio_db', 'spur_ratio_db', 'error_snr_db')}})
    tracking = {}
    for name in trackers:
        def settle(start):
            for end in range(start+16, len(rows)+1):
                if np.sqrt(np.mean([r[name+'_relative_error_rms']**2 for r in rows[end-16:end]])) < .002:
                    return {'blocks': end-start, 'milliseconds': (end-start)*args.block_size/baseline.FS*1e3}
            return None
        tracking[name] = {'startup': settle(0), 'step_recovery': settle(args.blocks//2) if scenario == 'step' else None,
                          'held_updates': sum(r[name+'_status'] != 'updated' for r in rows),
                          'max_causality_gap': max(abs(rows[i][name+'_gain_used']-rows[i-1][name+'_gain_next']) for i in range(1, len(rows)))}
    write_json(directory/'summary.json', {'foreground': fg, 'tracking': tracking, 'windows': summary,
               'foreground_time_ms': args.foreground_blocks*args.block_size/baseline.FS*1e3,
               'backend_overloads': sum(r['backend_overloads'] for r in rows),
               'settling_rule': 'first completed 16-block RMS relative gain error <0.2%; evaluator only'})
    print(f'{waveform}/{scenario}/seed{seed}: hybrid initial={rows[0]["hybrid_gain_used"]:.6f}, '
          f'final SNDR/ratio={summary[[r["window"] == "final_quarter" and r["method"] == "hybrid" for r in summary].index(True)]["spectral_ratio_db"]:.2f}', flush=True)
    return rows, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent/'output'/'hybrid_tracking')
    parser.add_argument('--blocks', type=int, default=256)
    parser.add_argument('--block-size', type=int, default=32768)
    parser.add_argument('--foreground-blocks', type=int, default=16)
    parser.add_argument('--seeds', nargs='+', type=int, default=[11, 22, 33])
    parser.add_argument('--scenarios', nargs='+', choices=['constant', 'ramp', 'step'], default=['constant', 'ramp', 'step'])
    parser.add_argument('--waveforms', nargs='+', choices=['sine', 'multitone'], default=['sine', 'multitone'])
    args = parser.parse_args(argv)
    if args.blocks < 64 or args.blocks % 4 or args.block_size < 1024 or args.block_size % 2 or args.foreground_blocks < 1:
        parser.error('Use blocks >=64 divisible by 4, even block-size >=1024, and foreground-blocks >=1')
    if any(len(set(v)) != len(v) for v in (args.seeds, args.scenarios, args.waveforms)):
        parser.error('Do not repeat seeds/scenarios/waveforms')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('Choose a new or empty output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    source = [Path(__file__), Path(plant.__file__), Path(baseline.__file__),
              Path(inspect.getfile(DitherGainTracker)), Path(inspect.getfile(write_json))]
    write_json(args.output/'configuration.json', {**vars(args), 'output': str(args.output.resolve()),
               'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source},
               'normal_time_ms': args.blocks*args.block_size/baseline.FS*1e3,
               'foreground_time_ms': args.foreground_blocks*args.block_size/baseline.FS*1e3,
               'comparison': 'identical probe-on captures; separate paired-noise foreground probe-off control'})
    all_summary, first_seed = [], {}
    for waveform in args.waveforms:
        for scenario in args.scenarios:
            for seed in args.seeds:
                rows, summary = run_case(args, scenario=scenario, waveform=waveform, seed=seed)
                all_summary += summary
                if seed == args.seeds[0]:
                    first_seed[waveform, scenario] = rows
    write_csv(args.output/'summary_by_seed.csv', all_summary)
    aggregate = []
    keys = sorted({(r['waveform'], r['scenario'], r['window'], r['method']) for r in all_summary})
    for key in keys:
        selected = [r for r in all_summary if tuple(r[k] for k in ('waveform', 'scenario', 'window', 'method')) == key]
        row = dict(zip(('waveform', 'scenario', 'window', 'method'), key))
        for metric in ('spectral_ratio_db', 'spur_ratio_db', 'error_snr_db'):
            v = [r[metric] for r in selected]
            row[metric+'_mean'] = float(np.mean(v))
            row[metric+'_sd'] = float(np.std(v, ddof=1)) if len(v) > 1 else 0.
        aggregate.append(row)
    write_csv(args.output/'summary.csv', aggregate)
    for waveform in args.waveforms:
        fig, axes = plt.subplots(2, len(args.scenarios), figsize=(5*len(args.scenarios), 8), squeeze=False, layout='constrained')
        for col, scenario in enumerate(args.scenarios):
            records = first_seed[waveform, scenario]
            time_ms = [r['time_ms'] for r in records]
            axes[0, col].plot(time_ms, [r['true_gain_mean'] for r in records], 'k--', label='Truth (evaluator)')
            for name, color in [('foreground_frozen', '#db8324'), ('background', '#3280b9'), ('hybrid', '#35a36f')]:
                field = 'foreground_gain' if name == 'foreground_frozen' else name+'_gain_used'
                axes[0, col].plot(time_ms, [r[field] for r in records], color=color, label=name)
                axes[1, col].plot(time_ms, [r[name+'_spectral_ratio_db'] for r in records], color=color, label=name)
            axes[0, col].set_title(scenario)
            axes[0, col].set_ylabel('Applied gain estimate')
            axes[1, col].set_ylabel('SNDR / total-tone ratio (dB)')
            axes[1, col].set_xlabel('Normal operation (ms); foreground time excluded')
            for ax in axes[:, col]:
                ax.grid(alpha=.25)
        axes[0, 0].legend(fontsize=8)
        fig.suptitle(f'{waveform}: causal foreground / background / hybrid | first seed')
        fig.savefig(args.output/f'hybrid_{waveform}.png', dpi=160)
        plt.close(fig)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
