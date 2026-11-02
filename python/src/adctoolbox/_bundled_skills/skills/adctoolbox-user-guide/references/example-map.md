# ADCToolbox Example Map

Use this file when you want a real script to adapt. The paths below match the
current packaged examples under `python/src/adctoolbox/examples/`.

## Start Here

- Dither injection locations, PN construction, identification versus noise
  randomization, and architecture-specific limits:
  `11_calibration/DITHER_GUIDE.md`. Use `exp_cal08_hdc_fixed.py` for fixed-point
  three-PN HDC; `exp_cal09_pn_architectures.py` for SAR paired bit weights,
  TI timing observability and Delta-sigma probe subtraction. These are example
  models, not universal calibration APIs or synthesized circuits.
- Calibration workflow and capability inventory:
  `11_calibration/CALIBRATION_SYSTEM.md`. Choose foreground/background, then
  correction form, memory and architecture; distinguish public APIs from examples.
- FFT fundamentals and amplitude scaling rules:
  `02_spectrum/exp_s00_fft_fundamentals.py`
- Environment / smoke test:
  `01_basic/exp_b01_environment_check.py`
- Coherent vs non-coherent sampling:
  `01_basic/exp_b02_coherent_vs_non_coherent.py`
- Simplest FFT metrics:
  `02_spectrum/exp_s01_analyze_spectrum_simplest.py`
- Interactive spectrum exploration:
  `02_spectrum/exp_s02_analyze_spectrum_interactive.py`
- Save or reuse figures:
  `02_spectrum/exp_s03_analyze_spectrum_savefig.py`
- SAR FFT-length sweep near Nyquist:
  `02_spectrum/exp_s09_sar_fft_length_near_nyquist.py`
- Noise-shaped quantization spectrum:
  `10_oversampling/exp_o01_noise_shaping_spectrum.py`
- Pipeline dither background gain calibration, convergence and drift tracking:
  `11_calibration/exp_cal01_dither_background.py`.
  Read the adjacent `README.md` for the injection model, causal updates and
  frozen foreground/probe-off controls. The plant remains an example;
  `DitherGainTracker` and `fit_pipeline_gain_sine` are now public gain interfaces.
- Dither mechanisms: gain, linear memory, capacitor switching, inverse cubic,
  randomization and identifiability failures:
  `11_calibration/exp_cal02_dither_coverage.py`; read adjacent
  `DITHER_COVERAGE.md` for equations and limits. The foreground fits here are
  mechanism-specific baselines, not a general polynomial fitting API.
- Direct polynomial/MLP foreground correction with an independent reference:
  `11_calibration/exp_cal03_foreground_nonlinear.py`.
- Foreground-initialized background gain tracking:
  `11_calibration/exp_cal04_hybrid_tracking.py`.
  Read `11_calibration/FOREGROUND_AND_HYBRID.md`; public API snippets are in
  `references/calibration-workflows.md`.
- Nonlinear history-feature excitation and multitone generalization:
  `11_calibration/exp_cal05_foreground_excitation.py` consumes a completed
  `exp_cal03` run and changes training excitation at fixed polynomial structure
  and sample budget. Single-tone test performance does not establish multitone
  correction accuracy, even when the numerical design rank is full.
- TI statistical background timing control:
  `08_time_interleave/exp_ti02_autocorr_background_skew_calibration.py`.
  This older demo lacks quantization and continuous drift evaluation and
  selects a history-best SFDR result; do not claim general blind tracking validation.

## Example Families

- Spectrum analysis:
  start in `02_spectrum/`
- Signal generation and impairment injection:
  start in `03_generate_signals/`
- Analog debug:
  start in `04_debug_analog/`
- Digital calibration and DOUT debug:
  start in `05_debug_digital/`
- Foreground/background calibration model selection:
  start with `11_calibration/CALIBRATION_SYSTEM.md`; existing weight examples
  stay in `05_debug_digital/`, TI examples in `08_time_interleave/`
- Toolset dashboards:
  start in `06_use_toolsets/`
- Metric and frequency conversions:
  start in `07_conversions/`
- Oversampling and noise shaping:
  start in `10_oversampling/`

## High-Value Files

- Signal generation:
  `03_generate_signals/exp_g01_generate_signal_demo.py`
- Sine fitting:
  `04_debug_analog/exp_a01_fit_sine_4param.py`
- Error by phase:
  `04_debug_analog/exp_a03_analyze_error_by_phase.py`
- Full weight calibration:
  `05_debug_digital/exp_d02_cal_weight_sine.py`
- SAR unit-cap mismatch without calibration:
  `05_debug_digital/exp_d15_sar_unit_cap_mismatch_uncal_spectra.py`
- SAR redundancy and unit-cap mismatch Monte Carlo calibration:
  `05_debug_digital/exp_d16_sar_unit_cap_mismatch_mc.py`
- SAR MSB +1% error, strict binary vs third-weight repeat calibration:
  `05_debug_digital/exp_d17_sar_msb_error_binary_vs_repeat_calibration.py`
- Redundant SAR unit-cap mismatch calibration versus training length:
  `05_debug_digital/exp_d18_sar_redundant_mismatch_training_length_sweep.py`
- AOUT dashboard:
  `06_use_toolsets/exp_t01_aout_dashboard_single.py`
- DOUT dashboard:
  `06_use_toolsets/exp_t03_dout_dashboard_single.py`
- In-band extraction with MATLAB-compatible `ifilter`:
  `10_oversampling/exp_o02_ifilter_band_analysis.py`
- NTF theory and performance-vs-OSR sweep:
  `10_oversampling/exp_o03_ntfperf_perfosr.py`

## Practical Notes

- The packaged examples are what `adctoolbox-get-examples` copies into a user workspace.
- Some older docs refer to outdated filenames. Prefer the paths in this file.
- Keep the example frequency conventions:
  `fs` and `Fin` are in Hz for spectrum and signal generation.
- Calibration examples usually use normalized `freq=Fin/Fs`.
- The toolset examples are the fastest way to see how multiple helpers are
  composed together.

## Advanced examples

For tasks covered by `references/advanced-debug.md`, adapt these
packaged scripts:

- Dashboards (multi-plot summaries):
  `06_use_toolsets/exp_t01_aout_dashboard_single.py`,
  `exp_t02_aout_dashboard_batch.py`,
  `exp_t03_dout_dashboard_single.py`,
  `exp_t04_dout_dashboard_batch.py`
- Phase-plane:
  `04_debug_analog/exp_a41_analyze_phase_plane.py`,
  `exp_a42_analyze_error_phase_plane.py`
- Bit-level / overflow / ENOB sweep:
  `05_debug_digital/exp_d11_bit_activity.py`,
  `exp_d12_sweep_bit_enob.py`,
  `exp_d14_overflow_check.py`,
  `exp_d15_sar_unit_cap_mismatch_uncal_spectra.py`,
  `exp_d16_sar_unit_cap_mismatch_mc.py`,
  `exp_d17_sar_msb_error_binary_vs_repeat_calibration.py`,
  `exp_d18_sar_redundant_mismatch_training_length_sweep.py`
- Error decomposition (by-phase / by-value / harmonic / PDF / spectrum / autocorr / envelope):
  `04_debug_analog/exp_a02_*`, `exp_a03_*`, `exp_a11_*`, `exp_a12_*`,
  `exp_a21_*` through `exp_a25_*`
- Static nonlinearity / INL from sine or ramp:
  `04_debug_analog/exp_a31_fit_static_nonlin.py`,
  `exp_a32_inl_from_sine_sweep_length.py`,
  `exp_a33_inl_from_ramp.py`

Cap-array → normalized weights (`convert_cap_to_weight`) is not
packaged as a standalone example; the inline snippet in
`references/advanced-debug.md` is the canonical reference.
