%% Verify plotspec MaxSpur marker/lobe visual convention

fprintf('[run_plotspec_marker] Starting MaxSpur marker tests...\n');

N = 8192;
Fs = 1;
sideBin = 1;
n = 0:(N-1);
sig = 0.49 * sin(2*pi*997*n/N) + 0.49 * 10^(-60/20) * sin(2*pi*2501*n/N);

fig = figure('Visible', 'off');
plotspec(sig, Fs, 1, 5, 'sideBin', sideBin, 'label', 1, 'disp', 1, 'window', 'hann');
ax = gca;

[expected_marker_db, expected_lobe_db, expected_lobe_freq, expected_integrated_db] = ...
    expected_maxspur_marker(sig, Fs, sideBin);

diamond = findobj(ax, 'Type', 'line', 'Marker', 'd');
assert(numel(diamond) == 1, 'Expected exactly one MaxSpur diamond marker');
marker_y = get(diamond, 'YData');
assert(abs(marker_y(1) - expected_marker_db) < 1e-9, ...
    'MaxSpur marker must use center-bin per-bin power');
assert(abs(marker_y(1) - expected_integrated_db) > 1.0, ...
    'Test case should distinguish per-bin marker from integrated spur power');

lobe_lines = findobj(ax, 'Type', 'line', 'LineStyle', '--');
matched_lobe = [];
for ii = 1:numel(lobe_lines)
    x = get(lobe_lines(ii), 'XData');
    y = get(lobe_lines(ii), 'YData');
    if numel(x) == numel(expected_lobe_freq) && ...
            max(abs(x(:) - expected_lobe_freq(:))) < 1e-12 && ...
            max(abs(y(:) - expected_lobe_db(:))) < 1e-9
        matched_lobe = lobe_lines(ii);
        break;
    end
end
assert(~isempty(matched_lobe), 'Expected MaxSpur lobe highlight line was not found');

close(fig);
fprintf('[run_plotspec_marker] All MaxSpur marker tests passed.\n');

function [marker_db, lobe_db, lobe_freq, integrated_db] = expected_maxspur_marker(sig, Fs, sideBin)
    N = numel(sig);
    Nd2 = floor(N/2) + 1;
    inbandEnd = Nd2;
    n = 0:(N-1);
    win = 0.5 * (1 - cos(2*pi*n/N));

    tdata = sig ./ 1;
    tdata = tdata - mean(tdata);
    tdata = tdata .* win / sqrt(mean(win.^2));

    spec = abs(fft(tdata)).^2;
    spec(1) = 0;
    spec = spec / (N^2) * 16;
    spec = spec(1:Nd2);
    if mod(N, 2) == 0
        spec(end) = spec(end) / 2;
    end

    [~, bin] = max(spec(1:inbandEnd));
    spec(max(bin-sideBin,1):min(bin+sideBin,Nd2)) = 0;
    spec(1:sideBin) = 0;
    spec_inband = spec(1:inbandEnd);

    [~, sbin] = max(spec_inband);
    spur_start = max(sbin-sideBin, 1);
    spur_end = min(sbin+sideBin, inbandEnd);

    marker_db = 10*log10(spec_inband(sbin) + 10^(-20));
    lobe_db = 10*log10(spec_inband(spur_start:spur_end) + 10^(-20));
    lobe_freq = ((spur_start:spur_end)-1) / N * Fs;
    integrated_db = 10*log10(sum(spec_inband(spur_start:spur_end)) + 10^(-20));
end
