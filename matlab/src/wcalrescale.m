function [weightS, offsetS, postcalS, idealS, errS, scaleFactor] = wcalrescale(weight, offset, postcal, ideal, err, varargin)
%WCALRESCALE Rescale wcalsin outputs to a chosen ADC reference scale.
%
%   [weightS, offsetS, postcalS, idealS, errS, scaleFactor] =
%       WCALRESCALE(weight, offset, postcal, ideal, err, 'Scale', s)
%
%   [weightS, offsetS, postcalS, idealS, errS, scaleFactor] =
%       WCALRESCALE(..., 'TargetWeights', nominalWeights)
%
%   [weightS, offsetS, postcalS, idealS, errS, scaleFactor] =
%       WCALRESCALE(..., 'TargetSinePeak', A)
%
%   WCALSIN fixes the fitted fundamental sine magnitude to one so that the
%   least-squares calibration problem is identifiable. Its weight, postcal,
%   ideal, and err outputs are therefore in solver-unit-sine scale. This
%   helper applies a single linear scale factor before dBFS or NSD
%   interpretation against an ADC voltage/code full-scale convention.
%
%   Exactly one scale source must be supplied:
%     - Scale: direct linear scale factor.
%     - TargetWeights: sum(TargetWeights) / sum(weight).
%     - TargetSinePeak: maps solver unit sine peak 1.0 to the specified peak.
%
%   Cell-array postcal/ideal/err outputs from multi-dataset WCALSIN are
%   supported. Ratio metrics are not inputs to this helper and should be left
%   unchanged by the caller.

    if nargin < 5
        error('wcalrescale:NotEnoughInputs', ...
              'weight, offset, postcal, ideal, and err are required.');
    end

    p = inputParser;
    addParameter(p, 'Scale', [], @(x) isempty(x) || (isnumeric(x) && isscalar(x)));
    addParameter(p, 'TargetWeights', [], @(x) isempty(x) || isnumeric(x));
    addParameter(p, 'TargetSinePeak', [], @(x) isempty(x) || (isnumeric(x) && isscalar(x)));
    parse(p, varargin{:});

    hasScale = ~isempty(p.Results.Scale);
    hasTargetWeights = ~isempty(p.Results.TargetWeights);
    hasTargetSinePeak = ~isempty(p.Results.TargetSinePeak);
    if (hasScale + hasTargetWeights + hasTargetSinePeak) ~= 1
        error('wcalrescale:AmbiguousScale', ...
              'Provide exactly one of Scale, TargetWeights, or TargetSinePeak.');
    end

    if hasScale
        scaleFactor = validateScale(p.Results.Scale, 'Scale');
    elseif hasTargetSinePeak
        scaleFactor = validateScale(p.Results.TargetSinePeak, 'TargetSinePeak');
    else
        validateNumericVector(weight, 'weight');
        validateNumericVector(p.Results.TargetWeights, 'TargetWeights');
        sourceSum = sum(weight(:));
        targetSum = sum(p.Results.TargetWeights(:));
        if ~isfinite(sourceSum) || sourceSum == 0
            error('wcalrescale:InvalidWeightSum', ...
                  'sum(weight) must be finite and non-zero.');
        end
        if ~isfinite(targetSum) || targetSum == 0
            error('wcalrescale:InvalidTargetWeightSum', ...
                  'sum(TargetWeights) must be finite and non-zero.');
        end
        scaleFactor = targetSum / sourceSum;
    end

    weightS = weight * scaleFactor;
    offsetS = offset * scaleFactor;
    postcalS = scaleValue(postcal, scaleFactor);
    idealS = scaleValue(ideal, scaleFactor);
    errS = scaleValue(err, scaleFactor);
end

function scale = validateScale(value, name)
    scale = double(value);
    if ~isfinite(scale) || scale == 0
        error('wcalrescale:InvalidScale', '%s must be finite and non-zero.', name);
    end
end

function validateNumericVector(value, name)
    if isempty(value)
        error('wcalrescale:EmptyWeights', '%s must not be empty.', name);
    end
    if ~isnumeric(value) || any(~isfinite(value(:)))
        error('wcalrescale:InvalidWeights', ...
              '%s must contain only finite numeric values.', name);
    end
end

function out = scaleValue(value, scaleFactor)
    if iscell(value)
        out = cell(size(value));
        for ii = 1:numel(value)
            out{ii} = value{ii} * scaleFactor;
        end
    else
        out = value * scaleFactor;
    end
end
