# Foreground nonlinear correction and hybrid tracking

The reusable Python interfaces are in `adctoolbox.calibration` and also exported
from `adctoolbox`. Existing sine-weight and TI calibration calls are unchanged.

## Public interfaces

| Interface | Purpose and result |
| --- | --- |
| `build_calibration_features(samples, history=..., state=...)` | Build aligned current/previous sample features; returns features, local sample indices and continuation state |
| `fit_calibration_polynomial(features, reference, degree=..., ridge=...)` | Direct supervised correction including cross terms; returns model and fitting diagnostics |
| `fit_calibration_mlp(features, reference, validation_features=..., validation_reference=...)` | Tanh residual network with a frozen affine baseline; returns validation-selected model, diagnostics and loss history |
| `apply_calibration(features, model)` | Frozen application; returns corrected signal and marginal training-range flags |
| `fit_pipeline_gain_sine(captures, frequency)` | Dedicated probe-off Pipeline sine fit using coarse/residue observations; returns inverse-residue gain estimate and diagnostics |
| `DitherGainTracker(...)` | Observable-only gain correlation estimator with apply/update/reset operations |
| `apply_gain_calibration(...)` | Shared frozen Pipeline gain correction with subtractive PN removal |

Models returned by the polynomial/MLP fitters are JSON-compatible dictionaries.
Save the `model` field using `json.dump` and load it with `json.load`. Normalization,
coefficients and input training ranges travel with the model. Application does not
refit, renormalize against a new capture, or alter model parameters. Keep channel
order, history length, sample alignment and units the same as during fitting.
Feature state belongs to the stream, not to the saved model.

### Alignment and reference contract

For each independent training record, call `build_calibration_features` with
`state=None`. Use its `sample_indices` to select the corresponding reference
samples. It discards startup rows lacking history. For a continuous stream, pass
the returned `state` into the next block. Do not connect independent records.

The reference must be an aligned measurement or a justified signal model. The
fitters do not know ADC truth and do not manufacture reference labels. A reference
channel's gain, bandwidth, timing and distortion errors become calibration errors
unless separately characterized. Fitting a sine to a distorted ADC output removes
harmonics from the label, but preserves that output's fundamental gain and phase;
it cannot establish absolute input accuracy by itself.

The polynomial basis includes every monomial up to the requested total degree.
Training-only feature standardization and ridge regularization improve numerical
behavior, but cannot supply missing excitation. Review `design_rank` and
`rank_deficient`. Parameter count grows combinatorially; more than 4096 terms is
rejected. An outside-training-range mask detects marginal range violations only,
not joint feature coverage, identifiability or monotonicity.

The MLP uses a single tanh hidden layer, a linear output, and a fixed affine
baseline fitted on the training set. Its residual target is normalized using
training data. SciPy L-BFGS trains all network weights; independent validation
reference MSE selects an initial/accepted/final iterate. A maximum-iteration
termination is reported as such, not silently called optimizer convergence.
The iteration budget is not a count of mini-batch epochs. No PyTorch dependency
is needed. Held-out test data must never be supplied as validation data.

## exp_cal03: nonlinear foreground benchmark

From the copied examples directory:

```bash
python 11_calibration/exp_cal03_foreground_nonlinear.py
```

The default is 32 training and 8 validation records per case, 8192 points each,
two plants, and three seeds. The larger acceptance experiment uses:

```bash
python 11_calibration/exp_cal03_foreground_nonlinear.py --records 400 --validation-records 40 --output output/foreground_acceptance
```

The fixed fitting stride is 16. Thus the larger run captures 3,276,800 training
points per case and fits on 204,800 rows; validation uses 20,480 selected rows.
Reference sine fits use the full captures. Every test waveform is evaluated at
all 8192 samples. This is separate from the earlier GCN paper reproduction.

### Device and observations

The static front end is `u = 0.99*x + 0.015*x^2 + 0.04*x^3`. The memory plant adds
`0.04*u_previous` before quantization; the static plant uses zero memory.
The ADC is a 14-bit midrise quantizer over [-1, 1] with 10 microvolt RMS input
noise. State and RNG continuity are tested independently. This is an explicit
behavioral nonlinear front-end model, not a transistor simulation or a full
multistage Pipeline ADC. Calibration sees only the final quantized output and
up to three preceding output samples, not the internal pre-quantization signal.

A separate 16-bit monitor captures the training input with 200 microvolt RMS
noise and nominal unity gain. A known-frequency least-squares projection extracts
its fundamental and DC; amplitude and phase are fitted. This observable reference
is the main label. Simulator clean input is reserved for test evaluation. A
separate baseline learns a sine fit of the distorted ADC output instead, exposing
reference bias. It is not mixed into the primary reference-channel results.

### Data splits and methods

Training and validation use separate seeds, phases, amplitudes and distinct tone
bins. Test tone bins are excluded from both. Amplitudes span [0.05, 0.90]; training
frequencies span approximately [0.02, 0.45] of sample rate. Tests at 0.467 also
probe frequency extrapolation, so the combined single-tone table is broader than
strict in-band interpolation. Single-tone training does not guarantee coverage
of arbitrary multitone histories; multi-tone and chirp tests explicitly check it.

All methods use the same captures and reference channel:

- Raw output; static affine; affine with three-sample history.
- Degree-three and degree-five polynomials, each with and without history.
- A 16-hidden-unit MLP with the same four input columns as the history polynomials.
- Degree-five history polynomial using the output-fitted reference (bias control).

The affine baseline is a fit of final output samples, not the bit-weight solver:
binary internal decisions are not available in this model. Method hyperparameters
are fixed before test evaluation. MLP validation selects the saved iterate;
polynomial degrees are reported separately, not chosen by test performance.

Tests cover 15 single-tone amplitude/frequency combinations, two- and three-tone
signals, a chirp, amplitude 0.98 overload stress, and a changed device (gain +2%,
cubic coefficient +50%). The last two are separate stress groups, not pooled
into ordinary performance. Report clipping counts and domain flags alongside
performance; clipped information is not recoverable by a general inverse map.

Single-tone ratios are SNDR/SFDR. Multi-tone ratios use total desired-tone power
and the strongest desired tone respectively. Chirp quality uses time-domain
error only. Absolute error SNR and RMSE compare with evaluator truth without gain,
phase or offset fitting. Summary standard deviations are across seed-wise means,
after averaging conditions within each seed.

Artifacts include configuration and source hashes, per-record split manifests,
JSON models, MLP training/validation history, per-test metrics, aggregate CSV/JSON,
and a comparison figure. A nonempty output directory is rejected.

## exp_cal05: joint excitation coverage control

The single-tone-trained history polynomial in `exp_cal03` can perform well on
held-out single tones yet fail badly on multi-tone inputs. Numerical full rank
and marginal feature-range coverage are insufficient evidence of generalization.
For an ideal zero-DC sine, four consecutive samples satisfy
`x0*x2 + x2**2 - x1**2 - x1*x3 = 0`, even as amplitude, phase and frequency vary.
Distortion and noise perturb this relation, but adding many single-tone records
does not automatically provide independent excitation of all nonlinear history
features. Multi-tone captures probe combinations absent from that training set.

Run the fixed-model control after `exp_cal03`:

```bash
python 11_calibration/exp_cal05_foreground_excitation.py --baseline output/foreground_acceptance --output output/excitation_acceptance
```

The experiment retains record count, samples per record, fitting stride,
polynomial degrees and regularization. Half the new captures are single tones,
half are two tones, with summed peak amplitude budget in [0.05, 0.90]. Their
individual tone bins exclude the baseline validation/test frequencies. It refits
affine history, static degree-five, and history degree-three/five models. It does
not retrain the MLP: the original single-tone-trained MLP is explicitly labeled
as a reference. Model selection still does not use test performance.

The saved models are evaluated on exactly the original test captures. Report
single-tone and multi-tone quality separately. This is an additional excitation
diagnostic, not a replacement that hides the original single-tone-training failure.

## exp_cal04: foreground initialization plus background tracking

```bash
python 11_calibration/exp_cal04_hybrid_tracking.py --output output/hybrid_acceptance
```

This uses the same two-stage gain-error plant as `exp_cal01`, including analog
noise, quantization and probe-on/off controls. Its binary software-generated PN
is known to the estimator. The explicit LFSR probes used by the other mechanism
examples remain in `exp_cal02`; the public gain tracker accepts either source
when its stated excitation and independence assumptions hold.

For each case, acquire a separate probe-off sine at initial gain 3.88. Streaming
QR fits `q + c*r = A*sin + B*cos + DC`, fixing the coarse scale, and returns
`G_est = 1/c`. This avoids squaring the design matrix condition number.
Then compare on identical probe-on normal-operation captures:

- Nominal reconstruction (gain 4).
- Frozen foreground estimate.
- Background initialized at nominal gain 4.
- Hybrid initialized at the fitted foreground gain.
- Evaluator-only oracle using the instantaneous true gain.

A separate frozen foreground probe-off control uses the same input and paired
analog noise. Both trackers correct each block with the old estimate, then update
for the next block. They share the observation data and averaging rate 0.08;
only initialization differs. Static final estimates therefore approach the same
noise/lag tradeoff. Hybrid startup requires foreground acquisition time and is
not automatically better than frozen foreground correction in a stable device.

Defaults: three seeds, single/two-tone waveforms, constant/ramp/step scenarios,
256 blocks of 32768 points at 100 MS/s. Normal operation spans 83.886 ms; the
16-block foreground acquisition costs 5.243 ms separately. Step gain is 4.08;
the ramp goes from 3.88 to 4.12 over the middle half of the run. These are tracking
stress profiles, not measured PVT time constants.

Each case saves block trajectories, initial foreground fit, first-16-block and
final-quarter metrics, and active-ramp/step windows. Startup/recovery uses the
first completed 16-block RMS relative gain-error window below 0.2%, solely as an
evaluator diagnostic. Source hashes, seed summaries and plots are also saved.
Do not select historical best SFDR to represent the final active calibrator.

The former example names `DitherGainTracker`, `fit_foreground_gain` and
`reconstruct` remain compatible. The first two route to the public implementation;
`reconstruct` remains an array-returning wrapper around the new dict-returning
`apply_gain_calibration`. Memory/capacitor/nonlinear background helpers remain
architecture-specific example interfaces; they have not been silently promoted.

## Audit completed runs

```bash
python 11_calibration/audit_calibration_acceptance.py --foreground output/foreground_acceptance --hybrid output/hybrid_acceptance --excitation output/excitation_acceptance --output output/calibration_audit.json
```

The audit verifies source hashes, saves matching source snapshots, checks the
training/validation/test frequency separation, replays every frozen foreground
model on regenerated test captures, recomputes aggregate metrics, and verifies
hybrid initialization and block-to-block causality. It also reports MLP optimizer
termination instead of treating all completed training runs as convergence.
It does not repeat fitting or claim independent transistor-level validation.
Omit `--excitation` when only the first two experiments have been run.
