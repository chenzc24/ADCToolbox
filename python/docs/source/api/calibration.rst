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
:doc:`timeinterleave`. Pipeline background estimators currently live in the
packaged ``11_calibration/`` examples, with explicit physical models and
observation assumptions. See :doc:`../calibration` for the method inventory.
