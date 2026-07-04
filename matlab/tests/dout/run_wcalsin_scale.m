%% Regression checks for wcalsin output scale conversion

fprintf('[run_wcalsin_scale] Starting wcalsin scale tests...\n');

weight = [2, 1, 0.5];
offset = 0.25;
postcal = [1, 2, 3, 4];
ideal = [0.7, 1.6, 2.7, 3.8];
err = postcal - offset - ideal;
targetWeights = [1, 0.5, 0.25];

[weightS, offsetS, postcalS, idealS, errS, scaleFactor] = ...
    wcalrescale(weight, offset, postcal, ideal, err, ...
                'TargetWeights', targetWeights);

expectedScale = sum(targetWeights) / sum(weight);
assert(abs(scaleFactor - expectedScale) < 1e-15, ...
       'TargetWeights scale factor mismatch');
assert(max(abs(weightS - weight * expectedScale)) < 1e-15, ...
       'weight scale mismatch');
assert(abs(offsetS - offset * expectedScale) < 1e-15, ...
       'offset scale mismatch');
assert(max(abs(postcalS - postcal * expectedScale)) < 1e-15, ...
       'postcal scale mismatch');
assert(max(abs(idealS - ideal * expectedScale)) < 1e-15, ...
       'ideal scale mismatch');
assert(max(abs(errS - err * expectedScale)) < 1e-15, ...
       'err scale mismatch');
assert(max(abs((postcalS - offsetS - idealS) - errS)) < 1e-15, ...
       'scaled residual relation mismatch');

cellPost = {postcal, postcal * 2};
cellIdeal = {ideal, ideal * 2};
cellErr = {err, err * 2};
[~, ~, postCellS, idealCellS, errCellS, scalePeak] = ...
    wcalrescale(weight, offset, cellPost, cellIdeal, cellErr, ...
                'TargetSinePeak', 0.49);

assert(abs(scalePeak - 0.49) < 1e-15, ...
       'TargetSinePeak scale factor mismatch');
for ii = 1:numel(cellPost)
    assert(max(abs(postCellS{ii} - cellPost{ii} * 0.49)) < 1e-15, ...
           'cell postcal scale mismatch');
    assert(max(abs(idealCellS{ii} - cellIdeal{ii} * 0.49)) < 1e-15, ...
           'cell ideal scale mismatch');
    assert(max(abs(errCellS{ii} - cellErr{ii} * 0.49)) < 1e-15, ...
           'cell err scale mismatch');
end

fprintf('[run_wcalsin_scale] All wcalsin scale tests passed.\n');
