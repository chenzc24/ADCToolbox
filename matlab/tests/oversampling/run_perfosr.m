%% Unit tests for perfosr

fprintf('[run_perfosr] Starting perfosr tests...\n');

N = 4096;
n = 0:(N-1);
fin = 123 / N;
A = 0.5;

% Harmonic-only residual: corrected residual RMS scaling should recover
% approximately -60 dBc as 60 dB SNDR. The legacy *4 one-sided scaling reports
% about 3.01 dB too low.
hd2 = A * 10^(-60 / 20);
sig_hd2 = A * sin(2*pi*fin*n) + hd2 * sin(2*pi*2*fin*n);
[~, sndr_hd2, ~, ~] = perfosr(sig_hd2, 'osr', 1, 'disp', 0);
assert(abs(sndr_hd2 - 60) < 0.1, 'perfosr harmonic SNDR should be near 60 dB');

% Noisy sine: perfosr should match a direct non-incremental reference using
% one-sided RMS residual power and inclusive OSR band edges.
rng(123);
sig_noise = A * sin(2*pi*fin*n) + 1e-3 * randn(1, N);
osr_vec = [1, 4, 16, 32];
[osr_out, sndr, sfdr, enob] = perfosr(sig_noise, 'osr', osr_vec, 'disp', 0);
[sndr_ref, sfdr_ref, enob_ref] = reference_perfosr(sig_noise, osr_vec);

assert(max(abs(osr_out - osr_vec)) < 1e-12, 'perfosr changed OSR output order');
assert(max(abs(sndr - sndr_ref)) < 1e-9, 'perfosr SNDR mismatch vs reference');
assert(max(abs(sfdr - sfdr_ref)) < 1e-9, 'perfosr SFDR mismatch vs reference');
assert(max(abs(enob - enob_ref)) < 1e-12, 'perfosr ENOB mismatch vs reference');

% Incremental sweep must agree with evaluating the same OSR alone.
[~, sndr_single, sfdr_single, enob_single] = perfosr(sig_noise, 'osr', 4, 'disp', 0);
idx = find(osr_vec == 4, 1);
assert(abs(sndr_single - sndr(idx)) < 1e-12, 'single-OSR SNDR mismatch');
assert(abs(sfdr_single - sfdr(idx)) < 1e-12, 'single-OSR SFDR mismatch');
assert(abs(enob_single - enob(idx)) < 1e-12, 'single-OSR ENOB mismatch');

fprintf('[run_perfosr] All perfosr tests passed.\n');

function [sndr, sfdr, enob] = reference_perfosr(sig, osr)
    sig = sig(:);
    N = length(sig);
    [sig_fit, ~, mag] = sinfit(sig);

    err = sig - sig_fit;
    win = hannwin_local(N);
    err_windowed = err .* win / sqrt(mean(win.^2));

    err_spec = abs(fft(err_windowed)).^2 / N^2;
    err_spec = err_spec(1:floor(N/2)+1);
    if N > 1
        if mod(N, 2) == 0
            err_spec(2:end-1) = 2 * err_spec(2:end-1);
        else
            err_spec(2:end) = 2 * err_spec(2:end);
        end
    end

    sig_power = mag^2 / 2;
    sndr = zeros(1, length(osr));
    sfdr = zeros(1, length(osr));
    enob = zeros(1, length(osr));

    for ii = 1:length(osr)
        n_inband = floor(N / (2 * osr(ii))) + 1;
        n_inband = max(1, min(n_inband, length(err_spec)));
        noi_power = sum(err_spec(1:n_inband));
        spur_power = max(err_spec(1:n_inband));
        sndr(ii) = 10 * log10(sig_power / noi_power);
        sfdr(ii) = 10 * log10(sig_power / spur_power);
        enob(ii) = (sndr(ii) - 1.76) / 6.02;
    end
end

function w = hannwin_local(N)
    if N == 1
        w = 1;
    else
        n = (0:(N-1))';
        w = 0.5 * (1 - cos(2*pi*n/N));
    end
end
