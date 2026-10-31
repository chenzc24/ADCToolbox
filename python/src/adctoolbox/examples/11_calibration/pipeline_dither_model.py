"""Behavioral first-stage gain calibration helpers for exp_cal01.

Research/example interfaces, not a new top-level ADCToolbox API. Voltages use
input and backend ranges [-1, 1]. A seven-level coarse stage has nominal gain
4 and an ideal quantized backend. A known PN voltage is injected AFTER the
coarse decision and BEFORE the residue amplifier:

    q = coarse_quantize(x)
    r = Q_backend(G * (x - q + a*p) + residue_noise)
    corrected = q + r/G_est - a*p

With independent PN, no overload, an accurate probe amplitude and a locally
constant gain, cov(p, r)/(a*var(p)) estimates G. Finite-record input/probe
correlation is estimator noise. Quantization need not be perfectly independent
of PN, so this is an approximate statistical estimator, not an exact identity.
The plant alone receives the true gain. The calibrator receives observable
codes/PN only. Its estimate is updated AFTER correction of each data block.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PipelineConfig:
    nominal_gain: float = 4.0
    backend_bits: int = 12
    probe_amplitude: float = 0.0625
    input_noise_rms: float = 0.00028
    residue_noise_rms: float = 0.0002

    def __post_init__(self):
        if self.nominal_gain != 4.0:
            raise ValueError("This seven-level example uses nominal gain 4")
        if not isinstance(self.backend_bits, int) or not 2 <= self.backend_bits <= 24:
            raise ValueError("backend_bits must be an integer in [2, 24]")
        values = (self.probe_amplitude, self.input_noise_rms, self.residue_noise_rms)
        if not all(np.isfinite(v) for v in values) or self.probe_amplitude <= 0 or min(values[1:]) < 0:
            raise ValueError("Probe must be positive and noise RMS nonnegative, all finite")


class DitherPipeline:
    """Memoryless two-stage plant with persistent, independent RNG streams.

    The backend has 12 bits by default: nominally two effective coarse bits
    plus 12 backend bits give 14-bit ideal resolution. No DAC mismatch,
    nonlinear amplifier, aperture jitter or residue memory is modeled here.
    Call reset only for a new experiment, never between contiguous blocks.
    """

    def __init__(self, config=None, seed=1):
        self.config = config or PipelineConfig()
        self.seed = seed
        self.reset()

    def reset(self):
        streams = np.random.SeedSequence(self.seed).spawn(3)
        self._pn_rng, self._input_rng, self._residue_rng = [np.random.default_rng(s) for s in streams]
        self.sample_count = 0

    def convert(self, signal, gain, *, probe_enabled=True):
        signal = np.asarray(signal, dtype=float)
        if signal.ndim != 1 or not signal.size or not np.isfinite(signal).all():
            raise ValueError("signal must be a finite nonempty one-dimensional array")
        gains = np.broadcast_to(np.asarray(gain, dtype=float), signal.shape)
        if not np.isfinite(gains).all() or np.any(gains <= 0):
            raise ValueError("gain must be finite and positive")
        c = self.config
        # Always consume PN, including when disabled; independently seeded
        # probe-on/off plants then see exactly the same analog noise draws.
        pn = np.where(self._pn_rng.random(signal.size) < .5, -1., 1.)
        if not probe_enabled:
            pn.fill(0.)
        sampled = signal + self._input_rng.normal(0., c.input_noise_rms, signal.size)
        coarse_code = np.searchsorted(np.arange(-5, 6, 2)/8, sampled)
        coarse = (coarse_code - 3)/4
        analog_residue = gains * (sampled - coarse + c.probe_amplitude*pn)
        analog_residue += self._residue_rng.normal(0., c.residue_noise_rms, signal.size)
        levels = 2**c.backend_bits
        code = np.clip(np.floor((analog_residue+1)*levels/2), 0, levels-1).astype(np.int64)
        residue = (code+.5)*2/levels-1
        self.sample_count += signal.size
        return {"coarse": coarse, "backend": residue, "backend_code": code, "pn": pn,
                # True overload counters are evaluation diagnostics, not estimator inputs.
                "input_overloads": int(np.sum(abs(sampled) > 1)),
                "backend_overloads": int(np.sum(abs(analog_residue) >= 1))}


def reconstruct(coarse, backend, pn, gain_estimate, probe_amplitude):
    """Apply a frozen estimate, including subtractive PN removal."""
    if not np.isfinite(gain_estimate) or gain_estimate <= 0:
        raise ValueError("gain_estimate must be positive and finite")
    return np.asarray(coarse) + np.asarray(backend)/gain_estimate - probe_amplitude*np.asarray(pn)


class DitherGainTracker:
    """Blockwise correlation estimate followed by exponential averaging.

    No ideal input, true gain, frequency or foreground label is accepted.
    backend_code is an observable saturation guard. Reject an entire block
    on a rail hit; selecting only non-clipped samples can bias PN correlation.
    The caller applies gain_estimate before calling update for that block.
    """

    def __init__(self, probe_amplitude=.0625, initial_gain=4., learning_rate=.08,
                 backend_bits=12, gain_bounds=(2., 6.)):
        if not np.isfinite(probe_amplitude) or probe_amplitude <= 0:
            raise ValueError("probe_amplitude must be positive and finite")
        if not np.isfinite(learning_rate) or not 0 < learning_rate <= 1:
            raise ValueError("learning_rate must be in (0, 1]")
        if not isinstance(backend_bits, int) or not 2 <= backend_bits <= 24:
            raise ValueError("backend_bits must be in [2, 24]")
        if not (0 < gain_bounds[0] <= initial_gain <= gain_bounds[1] < np.inf):
            raise ValueError("initial_gain must lie in finite positive gain_bounds")
        self.probe_amplitude = probe_amplitude
        self.initial_gain = initial_gain
        self.learning_rate = learning_rate
        self.backend_bits = backend_bits
        self.gain_bounds = gain_bounds
        self.reset()

    def reset(self):
        self.gain_estimate = float(self.initial_gain)
        self.updates = 0

    def update(self, backend, pn, backend_code):
        r, p, codes = np.asarray(backend, float), np.asarray(pn, float), np.asarray(backend_code)
        if r.ndim != 1 or r.shape != p.shape or r.shape != codes.shape or r.size < 2:
            raise ValueError("backend, pn and backend_code must have matching 1D shapes with >=2 samples")
        if not np.isfinite(r).all() or not np.isfinite(p).all() or not np.isin(p, [-1., 0., 1.]).all():
            raise ValueError("Finite backend and PN in {-1, 0, 1} required")
        if not np.isfinite(codes).all() or np.any(codes != np.floor(codes)) or np.any((codes < 0) | (codes >= 2**self.backend_bits)):
            raise ValueError("Invalid backend codes")
        status, observed = "updated", None
        centered = p-p.mean()
        energy = float(centered@centered)
        if np.any((codes == 0) | (codes == 2**self.backend_bits-1)):
            status = "held_backend_rail"
        elif energy/r.size < .25:
            status = "held_probe_excitation"
        else:
            observed = float(centered@(r-r.mean())/(self.probe_amplitude*energy))
            if not self.gain_bounds[0] <= observed <= self.gain_bounds[1]:
                status = "held_gain_out_of_range"
            else:
                self.gain_estimate += self.learning_rate*(observed-self.gain_estimate)
                self.updates += 1
        return {"gain_next": self.gain_estimate, "observed_gain": observed, "status": status}


def fit_foreground_gain(captures, frequency):
    """Dedicated sine calibration, without an ideal input or true gain.

    Probe is off. Fit q + c*r = A*sin(w*n) + B*cos(w*n) + DC, fixing the
    coarse-code coefficient to one. Captures are consecutive blocks of that
    dedicated sine; its amplitude and phase are NOT supplied to the fit.
    Return G_est=1/c, to be frozen during subsequent normal operation.
    The constant coarse DAC scale and known tone frequency are assumptions.
    """
    if not np.isfinite(frequency) or not 0 < frequency < .5:
        raise ValueError("frequency must be normalized in (0, .5)")
    gram, rhs, count = np.zeros((4, 4)), np.zeros(4), 0
    for capture in captures:
        q, r = np.asarray(capture["coarse"]), np.asarray(capture["backend"])
        if q.ndim != 1 or q.shape != r.shape or not np.isfinite(q).all() or not np.isfinite(r).all():
            raise ValueError("Invalid foreground capture")
        if np.any(capture["pn"] != 0):
            raise ValueError("Foreground fit requires probe off")
        n = np.arange(count, count+len(q))
        design = np.column_stack([r, -np.sin(2*np.pi*frequency*n), -np.cos(2*np.pi*frequency*n), -np.ones(len(q))])
        gram += design.T@design
        rhs -= design.T@q
        count += len(q)
    coefficients, _, rank, singular = np.linalg.lstsq(gram, rhs, rcond=1e-12)
    if count < 4 or rank < 4 or coefficients[0] <= 0:
        raise ValueError("Foreground record does not identify a positive gain")
    return {"gain_estimate": float(1/coefficients[0]), "samples": count,
            "condition_number": float(np.sqrt(singular[0]/singular[-1])),
            "coefficients": coefficients.tolist(), "reference": "joint sine fit; frequency known, amplitude/phase/DC fitted"}
