%% Run all unit tests

scriptPath = mfilename('fullpath');
if isempty(scriptPath)
    searchDir = pwd;
else
    searchDir = fileparts(scriptPath);
end

matlabRoot = '';
for k = 1:8
    if isfolder(fullfile(searchDir, 'src')) && isfolder(fullfile(searchDir, 'tests'))
        matlabRoot = searchDir;
        break;
    end
    parentDir = fileparts(searchDir);
    if isequal(parentDir, searchDir)
        break;
    end
    searchDir = parentDir;
end

if isempty(matlabRoot)
    error('run_all:notFound', 'Could not locate matlab/ root from current folder.');
end

addpath(genpath(fullfile(matlabRoot, 'src')));
addpath(genpath(fullfile(matlabRoot, 'tests')));
addpath(fullfile(matlabRoot, 'data_generation'));
cd(fullfile(matlabRoot, 'data_generation'));

run_common

run_aout

run_oversampling

run_dout

jitterConfig = fullfile('test_dataset', 'jitter_sweep', 'config.csv');
if exist(jitterConfig, 'file')
    run_jitter_load
else
    fprintf('[run_all] Skipping run_jitter_load; missing %s. Run data_generation/gen_jitter_sweep_data.m first.\n', jitterConfig);
end
