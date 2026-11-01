# Foreground correction and background gain tracking

Read packaged `11_calibration/FOREGROUND_AND_HYBRID.md` for model assumptions,
reference construction, experiment commands and output interpretation.

Use a supplied, aligned reference for supervised correction. Training-reference
error becomes calibration error. `fit_static_nonlin` characterizes forward
distortion; use `fit_calibration_polynomial` for a trained direct correction.

For independent training, validation and test records:

```python
from adctoolbox import (
    build_calibration_features, fit_calibration_polynomial,
    fit_calibration_mlp, apply_calibration,
)

train = build_calibration_features(training_output, history=3)
valid = build_calibration_features(validation_output, history=3)
test = build_calibration_features(test_output, history=3)
train_reference = training_reference[train["sample_indices"]]
valid_reference = validation_reference[valid["sample_indices"]]

poly = fit_calibration_polynomial(train["features"], train_reference, degree=3)
mlp = fit_calibration_mlp(
    train["features"], train_reference,
    validation_features=valid["features"], validation_reference=valid_reference,
    hidden_units=16, max_iterations=200, seed=11,
)
corrected = apply_calibration(test["features"], poly["model"])
corrected_mlp = apply_calibration(test["features"], mlp["model"])
```

`corrected["calibrated_signal"]` is in the reference's units and corresponds to
`test["sample_indices"]`. The model dictionary can be JSON-serialized directly.
`outside_training_range` is a per-row marginal-range flag, not a guarantee about
joint feature coverage. Features are current-first, then lag-1, lag-2, etc.
For consecutive stream blocks, pass the returned feature `state` to the next
call. Reset to `state=None` for each independent waveform. Do not concatenate
records before making history features.

For Pipeline gain with a known probe injected after the coarse decision and
before the residue gain:

```python
from adctoolbox import fit_pipeline_gain_sine, DitherGainTracker

foreground_result = fit_pipeline_gain_sine(calibration_captures, frequency=fin_over_fs)
tracker = DitherGainTracker(initial_gain=foreground_result["gain_estimate"])
corrected = tracker.apply(capture["coarse"], capture["backend"], capture["pn"])
update = tracker.update(capture["backend"], capture["pn"], capture["backend_code"])
```

The foreground capture iterator contains consecutive blocks of a dedicated sine
with PN off. Pass normalized frequency, not Hz. Coarse DAC scale fixes the gain
reference. The runtime `capture` is a separate normal-operation observation.
Configure probe amplitude, backend bit count and gain bounds to match the plant;
defaults match the packaged example. Apply before update: `gain_used` belongs to
the current block, `gain_next` to the next one. A rail or excitation hold leaves
the estimate unchanged. `reset()` restores the configured initial estimate.
Omit foreground initialization to start at nominal gain. No clean input, true
gain or input-tone frequency belongs in a background update.

These snippets are exercised by
`tests/integration/test_user_guide_skill_examples.py`.
