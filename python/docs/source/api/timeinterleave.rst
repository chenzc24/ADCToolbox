Time-Interleaved ADC Analysis (timeinterleave)
==============================================

The ``timeinterleave`` module provides utilities for channel splitting,
mismatch extraction, spur prediction, and foreground correction in
time-interleaved ADCs.

See :doc:`../calibration` for foreground/background classification and the
scope of the packaged statistical timing-control example. The correction
function below applies supplied parameters; it does not estimate them online.

.. currentmodule:: adctoolbox

Data Layout
-----------

.. autofunction:: deinterleave
.. autofunction:: interleave

Mismatch Analysis
-----------------

.. autofunction:: extract_mismatch_sine
.. autofunction:: predict_spurs

Correction
----------

.. autofunction:: fractional_delay_fft
.. autofunction:: fractional_delay_farrow
.. autofunction:: calibrate_foreground
