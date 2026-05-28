%% Run all unit tests

thisDir = fileparts(mfilename('fullpath'));
matlabRoot = fileparts(thisDir);
addpath(genpath(fullfile(matlabRoot, 'src')));
addpath(genpath(thisDir));
cd(matlabRoot);

run_common

run_aout

run_dout

run_jitter_load
