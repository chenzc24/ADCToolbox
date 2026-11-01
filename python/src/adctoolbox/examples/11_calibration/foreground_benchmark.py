"""Behavioral foreground benchmark helpers; not a measured-ADC model.

Source-monitor labels are observable reference-channel measurements projected
onto the known training tone. Clean input is returned separately for evaluation.
"""
from dataclasses import dataclass, asdict

import numpy as np
from scipy.signal import lfilter

from adctoolbox import build_calibration_features


@dataclass(frozen=True)
class FrontendConfig:
    gain: float = .99
    quadratic: float = .015
    cubic: float = .04
    memory: float = .04
    bits: int = 14
    noise_rms: float = 1e-5
    monitor_noise_rms: float = 2e-4
    monitor_gain: float = 1.


class NonlinearFrontend:
    """u=g*x+k2*x**2+k3*x**3; ADC input=u+m*u_previous+noise.

    The memory term is a linear FIR after the static nonlinearity. Quantization
    is signed midrise over [-1, 1]. Persistent state and RNG permit continuous
    conversion. reset starts an independent capture.
    """
    def __init__(self, config, seed):
        self.config, self.seed = config, seed
        self.reset()

    def reset(self):
        self.previous = 0.
        self.rng = np.random.default_rng(self.seed)

    def convert(self, x):
        x = np.asarray(x, float)
        c = self.config
        u = c.gain*x+c.quadratic*x*x+c.cubic*x**3
        analog, state = lfilter([1., c.memory], [1.], u, zi=[c.memory*self.previous])
        self.previous = float(u[-1])
        analog += self.rng.normal(0, c.noise_rms, len(x))
        levels = 2**c.bits
        code = np.clip(np.floor((analog+1)*levels/2), 0, levels-1)
        return {"raw": (code+.5)*2/levels-1, "rail": (code == 0) | (code == levels-1),
                "overload": abs(analog) >= 1}


def tone_projection(observation, frequencies):
    """Fit amplitudes, phases and DC; only frequencies are supplied."""
    n = np.arange(len(observation))
    basis = np.column_stack([np.ones(len(n))] +
                            [f(2*np.pi*frequency*n) for frequency in frequencies for f in (np.sin, np.cos)])
    return basis@np.linalg.lstsq(basis, observation, rcond=None)[0]


def capture(config, *, size, seed, frequencies, amplitudes, phases, chirp=False, history=3):
    warmup = 64
    n = np.arange(-warmup-history, size)
    if chirp:
        # Sweep stays within Nyquist over the evaluated record.
        clean = .75*np.sin(2*np.pi*(.03*n+.40*n*n/(2*size))+.2)
    else:
        clean = sum(a*np.sin(2*np.pi*f*n+p) for f, a, p in zip(frequencies, amplitudes, phases))
    adc_seed, monitor_seed = np.random.SeedSequence(seed).spawn(2)
    converter = NonlinearFrontend(config, adc_seed)
    observed = converter.convert(clean)
    monitor = config.monitor_gain*clean + np.random.default_rng(monitor_seed).normal(0, config.monitor_noise_rms, len(clean))
    monitor = (np.clip(np.floor((monitor+1)*32768), 0, 65535)+.5)/32768-1
    raw = observed['raw'][warmup:]
    result = {"raw": raw, "truth": clean[warmup:], "monitor": monitor[warmup:],
              "overloads": int(observed['overload'][warmup+history:].sum()),
              "rails": int(observed['rail'][warmup+history:].sum())}
    if not chirp:
        result['reference'] = tone_projection(result['monitor'], frequencies)
        result['output_fit_reference'] = tone_projection(raw, frequencies)
    return result


def dataset(config, *, records, size, seed, stride, exclude_bins=()):
    rng = np.random.default_rng(seed)
    candidates = np.setdiff1d(np.arange(max(3, int(.02*size)) | 1, int(.45*size), 2), exclude_bins)
    if records > len(candidates):
        raise ValueError('Too many records for distinct training tone bins')
    bins = rng.choice(candidates, records, replace=False)
    features, labels, biased_labels, manifest = [], [], [], []
    for i, k in enumerate(bins):
        amplitude, phase = rng.uniform(.05, .90), rng.uniform(0, 2*np.pi)
        capture_seed = int(rng.integers(0, 2**31-1))
        c = capture(config, size=size, seed=capture_seed, frequencies=[k/size],
                    amplitudes=[amplitude], phases=[phase])
        built = build_calibration_features(c['raw'], history=3)
        select = built['sample_indices'][::stride]
        features.append(built['features'][::stride])
        labels.append(c['reference'][select])
        biased_labels.append(c['output_fit_reference'][select])
        manifest.append({'record': i, 'tone_bin': int(k), 'amplitude': float(amplitude),
                         'phase': float(phase), 'capture_seed': capture_seed,
                         'overloads': c['overloads'], 'rails': c['rails']})
    return {'features': np.vstack(features), 'reference': np.concatenate(labels),
            'output_fit_reference': np.concatenate(biased_labels), 'manifest': manifest,
            'plant': asdict(config)}
