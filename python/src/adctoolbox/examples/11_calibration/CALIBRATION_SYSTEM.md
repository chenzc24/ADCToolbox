# Calibration system: foreground and background

For Dither injection positions, PN statistics and architecture-specific
identification/correction, start with [DITHER_GUIDE.md](DITHER_GUIDE.md).

Choose **foreground or background by how parameters are identified and updated**.
Then describe the correction model independently: linear or nonlinear, memoryless
or with memory, and the ADC architecture and observable signals it requires.
This guide inventories the Python implementation on the calibration-expansion
branch. Public APIs, packaged simulation helpers and future work are explicitly
separated below.

## Two workflows, shared correction models

| Workflow | Parameter identification | Normal conversion | Existing starting point |
| --- | --- | --- | --- |
| Foreground | Dedicated acquisition with a controlled stimulus or reference; fit parameters before use | Apply frozen parameters; recalibration needs another dedicated interval | Sine-weight calibration; TI sine mismatch extraction |
| Background | Estimate from normal-operation observations, known injected probes, or justified signal statistics | Correct and update causally while conversion continues | Pipeline dither experiments; TI statistical timing example |

Both workflows can be simulated entirely in software, or implemented on chip.
CPU, FPGA and ASIC describe the implementation platform, not the calibration
workflow. Processing captured normal-operation data offline can model a
background algorithm if its observations, state and update order reproduce the
online process. Training a network on dedicated sine captures and then freezing
it is foreground calibration, even if its inference runs continuously on chip.

Foreground initialization followed by background tracking is a useful combination.
It shares the correction model and needs compatible parameter definitions and
state initialization. `exp_cal04_hybrid_tracking.py` compares this combined
startup with frozen foreground and nominal-initialized background paths.

## Classification axes

| Axis | Choices / examples | What it determines |
| --- | --- | --- |
| Identification workflow | Foreground / background | When and from what data parameters can be learned |
| Correction form | Affine / nonlinear | Mapping from declared observable inputs to corrected output |
| Temporal dependence | Memoryless / with memory | Whether correction needs earlier samples or persistent state |
| Architecture | SAR / Pipeline / time-interleaved ADC | Available decisions, subcodes, residuals and actuators |
| Identification information | Sine model, reference path, PN injection, switching, signal statistics | Conditions under which the parameters are identifiable |
| Correction destination | Digital reconstruction / analog trim | Whether estimated parameters change output processing or the converter itself |
| Maturity | Public API / packaged example / research or planned | What users can import and what still needs generalization |

Define linearity relative to the inputs. A weighted sum of bit decisions is
linear in those decisions and can correct capacitor-mismatch INL. A polynomial
can be linear in its fitted coefficients while remaining nonlinear in its input
code. A fixed FIR or recursive inverse has memory but need not be nonlinear.
Estimator averaging state is different from signal-path memory: a gain tracker
has history even though its frozen gain correction is memoryless.

## Implemented foreground workflows

| Method | Correction and required data | Entry point | Status |
| --- | --- | --- | --- |
| Sine-based bit weights | Affine reconstruction of binary decision columns; dedicated sine capture | `adctoolbox.calibrate_weight_sine`; `adctoolbox.calibration.calibrate_weight_sine_lite` | Public API; full and lite variants of one family |
| TI offset, gain and skew | Per-channel affine correction plus fractional delay; interleaved sine capture and channel count | `adctoolbox.extract_mismatch_sine`, then `adctoolbox.calibrate_foreground` | Public API; extraction and application are separate |
| Pipeline gain fit | Dedicated sine, coarse subcode and backend output; frozen inverse gain | `pipeline_dither_model.py`: `fit_foreground_gain`; run `exp_cal01_dither_background.py` | Packaged example |
| Pipeline mechanism-specific fits | Gain, linear memory, capacitor-switch mismatch or inverse cubic; dedicated sine and internal observables | `dither_mechanisms.py`: `foreground_fit`; run `exp_cal02_dither_coverage.py` | Packaged examples, including a specialized nonlinear baseline |
| Direct polynomial correction | Aligned supplied reference; arbitrary declared features, optional history and cross terms | `fit_calibration_polynomial` + `apply_calibration` | Public API; `exp_cal03_foreground_nonlinear.py` demonstrates independent-reference fitting |
| Residual MLP correction | Supplied training and separate validation reference; frozen affine baseline plus trained tanh network | `fit_calibration_mlp` + `apply_calibration` | Public API; same foreground example |

Pipeline gain fitting is also available as `fit_pipeline_gain_sine`, with shared
`apply_gain_calibration` reconstruction. The mechanism-specific examples live
in `11_calibration/`. Public weight examples remain
under `05_debug_digital/`; the TI examples remain under `08_time_interleave/`.

For bit weights, `bits` has shape `(N_samples, N_decisions)` and binary values.
A multi-bit stage subcode is not one binary decision; these example inputs are
not interchangeable. Full sine-weight results use solver-unit-sine scaling by
default. Use `scale_calibration_output` with the intended nominal weights before
interpreting absolute ADC full scale or dBFS.

`harmonic_order > 1` adds nuisance harmonics to the fitted reference in the full
weight solver. Its corrected output remains an affine bit-weight reconstruction;
this option does not implement polynomial inverse correction. Likewise,
`fit_static_nonlin` characterizes a forward distortion model; it is not a complete
inverse-calibration workflow.

The TI correction function applies supplied parameters; calling it on another
record does not re-estimate them. FFT skew correction has circular boundaries and
a per-channel bandwidth restriction. The Farrow alternative uses finite-tap
interpolation. Neither option by itself establishes a general stateful background
tracking API.

## Implemented background workflows

| Method | Observable information and estimator | Correction | Entry point / status |
| --- | --- | --- | --- |
| Pipeline gain | Known PN and backend residue; normalized covariance | Frozen inverse gain within each block, then PN subtraction | Public `DitherGainTracker` and `apply_gain_calibration`; `exp_cal01` / `exp_cal04` examples |
| Pipeline gain and linear memory | Present/delayed PN and residue; covariance system | Stateful inverse of the gain-plus-one-delay model | `MemoryTracker` + `MemoryCorrector` in `dither_mechanisms.py`; `exp_cal02_dither_coverage.py`; example |
| Capacitor mismatch | Known random capacitor-role switching and coarse codes; code-conditioned instrument | Switching-dependent affine reconstruction of observed residue/coarse code | `CapacitorTracker` + `capacitor_correct`; same module and runner; example |
| Inverse cubic nonlinearity | Four-level PN and residue; two independent moment conditions | `q + c1*r + c3*r**3 - a*p` | `NonlinearTracker` + `nonlinear_correct`; same module and runner; example |
| Joint capacitor / gain / memory / nonlinear model | Independent cap switching plus four-level present/delayed PN; three electronics moments followed by a deembedded cap moment | Stateful inverse cubic/memory path, probe subtraction, cap correction | `joint_dither_model.py` + `exp_cal06_joint_dither.py`; [research example](JOINT_DITHER.md), convergence must be checked |
| Joint convergence diagnosis and refinement | Same probe amplitude; retain moments separately for observed coarse-code pairs; compare EMA and cumulative averaging | Same joint correction path and capacitor moment | `joint_dither_convergence.py` + `exp_cal07_joint_convergence.py`; [research study](JOINT_CONVERGENCE.md), includes finite-sample and bias controls |
| TI timing skew | Adjacent-channel mean absolute differences and statistical assumptions | Digital estimator controls analog delay-line trim | `08_time_interleave/exp_ti02_autocorr_background_skew_calibration.py`; example |

The Pipeline gain interface is now public. The memory, capacitor-switch and
inverse-cubic trackers remain **example interfaces**. All model specific
injection points, ADC structures and accessible internal signals.
There is no universal estimator that can calibrate an arbitrary ADC using its
final output code alone.

Read `DITHER_COVERAGE.md` for each observation equation and excitation requirement.
PN is a known probe. It becomes useful because the chosen injection or switching
path exposes the unknown parameter in a measurable response. Scalar correlation
does not identify arbitrary nonlinear or memory errors. Delay regressors,
code-conditioned statistics or additional independent moments are needed for the
implemented mechanisms. Known injection amplitude is an assumption; gain and
unknown injection amplitude cannot generally be separated by one correlation.

The TI example is an older statistical-control demonstration. Its sampling model
does not include ADC quantization, captures restart their time origin, and its
final displayed result selects the best single-tone SFDR from history. It needs
continuous-stream, drift and current-parameter evaluation before sharing the
Pipeline tracking benchmark's validation claims.

## Current coverage and gaps

| Workflow | Affine / linear correction | Nonlinear correction |
| --- | --- | --- |
| Foreground | Public bit weights, TI correction and Pipeline gain fit; Pipeline memory example fit | Public supervised polynomial and MLP correction; specialized inverse-cubic example; general LUT still to package |
| Background | Public Pipeline PN gain tracker; memory and switching-dependent mismatch examples; TI analog timing-control example | Specialized inverse-cubic moment example; no general nonlinear-memory or neural-network tracker |

Earlier Pipeline polynomial, LUT, MLP and GCN comparisons remain repository
research experiments. The new generic polynomial/MLP APIs and foreground
benchmark are separate from that paper reproduction. See
`FOREGROUND_AND_HYBRID.md` for the implemented interfaces and reference contract;
earlier results remain in `docs/plans/2026-10-31-calibration-expansion.md`.

Dither randomization is a supporting technique, not necessarily calibration.
The threshold-INL randomization sweep in `exp_cal02_dither_coverage.py` estimates
no correction parameters: it demonstrates spur decorrelation and the consequences
of subtracting a known injected signal. Keep it separate from parameter tracking.

## Common architecture for future APIs

Use the following responsibilities when extracting reusable APIs from examples.
Polynomial/MLP fitting and Pipeline gain tracking now follow these boundaries;
they do not require a universal class hierarchy.

```text
ADC / probe model -> observable capture -> correction model -> corrected output
                              |                  ^
                              v                  |
                     parameter estimator ------ parameters

true input and true device parameters -> evaluator only
```

1. **ADC / probe model** owns physical error, quantization, clipping, injection
   and analog memory. It returns explicitly documented observable fields.
2. **Estimator** owns parameter fitting or adaptation. Foreground fitting uses
   dedicated reference data; background updates use allowed runtime observations.
3. **Correction model** applies a parameter snapshot, carrying signal history
   when needed. The same correction can serve both workflows.
4. **Evaluator** compares methods and computes metrics. Simulator truth and
   oracle parameters never feed the practical estimator or choose its updates.

Use consistent semantics for `fit`, `apply`, `update` and `reset`
interfaces. `fit` identifies parameters from a dedicated dataset; `apply` corrects
with a supplied snapshot; `update` changes the estimate using observable data;
`reset` deliberately clears the relevant estimator or signal-path state.
The public gain tracker implements apply/update/reset. Generic foreground models
use separate fit/apply functions and JSON model dictionaries; history state is
explicit in `build_calibration_features`. Older helpers retain their existing APIs.

For the current block-based Pipeline benchmark, correct block k with the parameters
available at its start, update after observing block k, and use the new parameters
for block k+1. Preserve PN state, analog memory, correction memory and time across
blocks. Other online schedules are possible, but must state their latency and
availability of observations.

Record input representation, coefficient units, reference assumptions, excitation
and rank checks, update status, and output scale. Flag saturation or inadequate
excitation rather than treating an unidentifiable update as successful calibration.

## Next implementation priorities

1. Extend the packaged polynomial/MLP foreground benchmark to architecture-specific
   stage-code inputs and a LUT baseline, retaining independent reference and test
   captures. Do not compare methods with different observable information as
   though their input budgets were identical.
2. Extend public gain calibration to other tested Pipeline mechanisms after
   documenting their architecture-specific observability and persistent state.
   Gain-only foreground initialization plus background tracking is implemented.
3. Bring the TI background example to the same continuous-stream evaluation
   standard: quantization, drift, current parameters, excitation failures and
   multiple input spectra.
4. Extend to SAR background weight identification, auxiliary-reference methods
   and nonlinear memory only after deriving their identifiable observation models.

Foreground validation needs held-out input frequencies, amplitudes and waveforms,
with parameters frozen during testing. Background validation needs startup,
steady-state fluctuation, ramp/step tracking, causal updates, block-boundary
invariance, probe overhead and failure cases. Both need nominal, frozen-foreground,
adaptive and truth-only diagnostic controls where applicable.

Existing experiment evidence is recorded in repository reports
`docs/experiments/2026-10-31-dither-background.md` and
`docs/experiments/2026-11-01-dither-coverage.md`, with joint-error results in
`docs/experiments/2026-11-01-joint-dither.md`. Results validate the stated models
and conditions, not arbitrary ADC architectures or silicon implementation cost.

The hardware-oriented three-PN HDC example is documented in
[HDC_FIXED.md](HDC_FIXED.md). Its integer arithmetic, serial divider and
register inventory are explicit; the memory and two-element DAC correlators
are extensions to the published HDC equations. The fixed-feedback capacitor
network and forward-cubic plant differ from the earlier joint experiment.
It is not yet synthesized RTL or a verified analog circuit. The dated
`docs/experiments/2026-11-02-hdc-fixed.md` report includes both successful
tone tests and DC/low-frequency headroom failures at unchanged dither peak.
