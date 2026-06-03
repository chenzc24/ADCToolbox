%ENSUREMATLABROOT Change current folder to the MATLAB simulation workspace.
%   Test and data-generation scripts use relative paths such as
%   test_dataset/ and test_output/. Calling them via run('subdir/script.m')
%   changes pwd to that subfolder; invoke this helper first so paths resolve
%   under data_generation/.

scriptPath = mfilename('fullpath');
if isempty(scriptPath)
    p = pwd;
else
    p = fileparts(scriptPath);
end
for k = 1:8
    if isfolder(fullfile(p, 'src')) && ...
            (isfolder(fullfile(p, 'tests')) || isfolder(fullfile(p, 'data_generation')))
        matlabRoot = p;
        addpath(genpath(fullfile(matlabRoot, 'src')));
        addpath(genpath(fullfile(matlabRoot, 'tests')));
        if isfolder(fullfile(matlabRoot, 'data_generation'))
            dataGenerationRoot = fullfile(matlabRoot, 'data_generation');
            addpath(dataGenerationRoot);
        else
            dataGenerationRoot = matlabRoot;
        end
        if ~strcmp(pwd, dataGenerationRoot)
            cd(dataGenerationRoot);
        end
        return;
    end
    pNext = fileparts(p);
    if isequal(pNext, p)
        break;
    end
    p = pNext;
end

error('ensureMatlabRoot:notFound', ...
    'Could not locate matlab/ root (expected src/ and tests/ or data_generation/).');
