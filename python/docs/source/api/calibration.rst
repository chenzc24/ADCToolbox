Calibration (calibration)
=========================

Start with :doc:`../calibration` to choose a foreground or background workflow
and distinguish public APIs from packaged simulation examples.

Foreground bit-weight identification
------------------------------------

These functions identify affine reconstruction weights from a dedicated sine
capture. The full and lite variants belong to the same calibration family.

.. autofunction:: adctoolbox.calibrate_weight_sine
.. autofunction:: adctoolbox.calibration.calibrate_weight_sine_lite

Scaling and identification diagnostics
--------------------------------------

These helpers support calibration; they are not separate identification methods.

.. autofunction:: adctoolbox.scale_calibration_output
.. autofunction:: adctoolbox.diagnose_calibration_matrix

Other calibration workflows
---------------------------

TI sine mismatch extraction and correction are documented in
:doc:`timeinterleave`. See :doc:`../calibration` for the method inventory and
:doc:`../calibration_workflows` for the new foreground and hybrid benchmarks.

Supervised foreground correction
--------------------------------

References must be supplied explicitly. These functions fit a direct correction
mapping, distinct from forward distortion characterization with
``fit_static_nonlin``. Models are JSON-compatible dictionaries.

.. autofunction:: adctoolbox.build_calibration_features
.. autofunction:: adctoolbox.fit_calibration_polynomial
.. autofunction:: adctoolbox.fit_calibration_mlp
.. autofunction:: adctoolbox.apply_calibration

Pipeline gain identification and shared correction
--------------------------------------------------

These interfaces assume a known probe injected after the coarse decision and
before the residue gain. They are not generic output-code-only calibrators.

.. autofunction:: adctoolbox.fit_pipeline_gain_sine
.. autofunction:: adctoolbox.apply_gain_calibration
.. autoclass:: adctoolbox.DitherGainTracker
   :members: apply, update, reset
